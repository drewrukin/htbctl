"""
HTBIntegration — HackTheBox API client.

Token lookup order:
  1. token= argument
  2. env_path file (if provided)
  3. ~/.config/htbctl/.env
  4. .env in current directory
  5. HTB_TOKEN environment variable (fallback)
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import dotenv_values

from . import __version__
from .exceptions import (
    HTBAuthError,
    HTBError,
    HTBMachineNotFoundError,
    HTBRateLimitError,
    HTBSpawnError,
)
from .models import SpawnedMachine


API_BASE = "https://labs.hackthebox.com/api/v4"
_ENV_SEARCH_PATHS = [
    Path.home() / ".config" / "htbctl" / ".env",
    Path(".env"),
]
_IP_RE = re.compile(
    r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$'
)

logger = logging.getLogger(__name__)


def _read_token_from_env_file(path: Path) -> Optional[str]:
    """Read HTB_TOKEN from a .env file without mutating os.environ."""
    if path.exists():
        values = dotenv_values(path)
        return values.get("HTB_TOKEN")
    return None


class HTBIntegration:
    """
    HackTheBox API client focused on machine lifecycle automation.

    Basic usage:
        htb = HTBIntegration(token="eyJ...")
        machine = htb.spawn("Cap")
        print(machine.ip)   # 10.10.11.xx
        htb.stop("Cap")

    Token from environment / file:
        htb = HTBIntegration()                      # ~/.config/htbctl/.env
                                                    # → .env in current directory
                                                    # → HTB_TOKEN env var
        htb = HTBIntegration(env_path="HTB/.env")  # explicit path

    Auto-stop with context manager:
        with HTBIntegration(token="...") as htb:
            machine = htb.spawn("Cap")
            print(machine.ip)
        # machine is stopped automatically

    Get a token at: https://app.hackthebox.com/profile/settings → App Tokens
    """

    SPAWN_INITIAL_WAIT = 20   # seconds before first poll
    SPAWN_POLL_INTERVAL = 10  # seconds between poll attempts
    SPAWN_MAX_ATTEMPTS = 16   # 20 + 16×10 = 180s total

    def __init__(
        self,
        token: Optional[str] = None,
        env_path: Optional[str] = None,
    ):
        if token:
            self._token = token
        else:
            self._token = self._find_token(env_path)

        if not self._token:
            raise ValueError(
                "HTB_TOKEN not set. Options:\n"
                "  HTBIntegration(token='eyJ...')\n"
                "  export HTB_TOKEN=eyJ...\n"
                "  echo 'HTB_TOKEN=eyJ...' > ~/.config/htbctl/.env\n\n"
                "Get a token at: https://app.hackthebox.com/profile/settings → App Tokens"
            )

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "User-Agent": f"htbctl/{__version__}",
        })
        self._spawned: dict[str, int] = {}  # name → machine_id (for auto-stop)

    @staticmethod
    def _find_token(env_path: Optional[str]) -> Optional[str]:
        """Find token from files, then fall back to env var. No side effects."""
        if env_path:
            token = _read_token_from_env_file(Path(env_path))
            if token:
                return token
        else:
            for path in _ENV_SEARCH_PATHS:
                token = _read_token_from_env_file(path)
                if token:
                    return token
        return os.getenv("HTB_TOKEN")

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _parse_response(self, r: requests.Response, endpoint: str) -> dict:
        if r.status_code == 401:
            raise HTBAuthError("Invalid or expired token")
        if r.status_code == 403:
            try:
                msg = r.json().get("message", "")
            except (ValueError, KeyError):
                msg = ""
            raise HTBError(f"Access denied (403). {msg}".strip())
        if r.status_code == 404:
            raise HTBMachineNotFoundError(f"Not found: {endpoint}")
        if r.status_code == 429:
            raise HTBRateLimitError("Rate limit exceeded — try again later")
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "text/html" in ct or r.text.lstrip().startswith("<!"):
            raise HTBAuthError("Invalid or expired token (got HTML instead of JSON)")
        try:
            return r.json()
        except ValueError as e:
            raise HTBError(f"Invalid JSON from API ({endpoint}): {e}")

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        try:
            r = self._session.request(method, f"{API_BASE}/{endpoint}", timeout=30, **kwargs)
            return self._parse_response(r, endpoint)
        except HTBError:
            raise
        except requests.exceptions.Timeout:
            raise HTBError(f"Request timed out: {endpoint}")
        except requests.exceptions.ConnectionError:
            raise HTBError("No connection to HackTheBox API")
        except requests.exceptions.HTTPError as e:
            raise HTBError(f"HTTP error: {e}")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        return self._request("GET", endpoint, params=params)

    def _post(self, endpoint: str, data: dict) -> dict:
        return self._request("POST", endpoint, json=data)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self) -> dict:
        """Verify authentication. Returns user info dict."""
        info = self._get("user/info").get("info", {})
        logger.info("Logged in as %s VIP=%s", info.get("name"), info.get("isVip"))
        return info

    # ── Machine info ──────────────────────────────────────────────────────────

    def get_machine_info(self, name: str) -> dict:
        """Get machine metadata by name."""
        data = self._get(f"machine/profile/{name}").get("info")
        if not data:
            raise HTBMachineNotFoundError(f"Machine '{name}' not found")
        return data

    def active_machine(self) -> Optional[dict]:
        """Return currently active machine info, or None."""
        try:
            return self._get("machine/active").get("info")
        except (HTBAuthError, HTBRateLimitError):
            raise
        except HTBError:
            return None

    def list_available(self, query: str = "", pages: int = 20) -> list[dict]:
        """List retired machines. Optional name filter."""
        machines = []
        for page in range(1, pages + 1):
            data = self._get(
                "machine/list/retired/paginated", params={"page": page}
            ).get("data", [])
            if not data:
                break
            for m in data:
                if not query or query.lower() in m.get("name", "").lower():
                    machines.append(m)
        return machines

    # ── Spawn / Stop ──────────────────────────────────────────────────────────

    def spawn(self, machine_name: str) -> SpawnedMachine:
        """
        Spawn a machine and wait for its IP (up to 3 minutes).

        If the machine is already running — waits for the IP without re-spawning.
        If a *different* machine is running — raises HTBSpawnError.
        Use --force / stop_active() first in that case.
        """
        info = self.get_machine_info(machine_name)
        machine_id: int = info["id"]
        os_name: str = info.get("os", "")
        difficulty: str = info.get("difficultyText", "")

        active = self.active_machine()
        if active:
            if active.get("id") == machine_id:
                logger.info("%s already running, waiting for IP...", machine_name)
            else:
                raise HTBSpawnError(
                    f"Another machine is active: {active.get('name')} (id={active.get('id')}). "
                    f"Stop it first or use stop_active()."
                )
        else:
            result = self._post("vm/spawn", {"machine_id": machine_id})
            if not result.get("success") and "deployed" not in result.get("message", ""):
                raise HTBSpawnError(result.get("message") or str(result))
            logger.info("Spawning %s...", machine_name)

        self._spawned[machine_name] = machine_id

        time.sleep(self.SPAWN_INITIAL_WAIT)
        ip = None
        for attempt in range(self.SPAWN_MAX_ATTEMPTS):
            try:
                active_info = self.active_machine() or {}
            except (HTBAuthError, HTBRateLimitError):
                raise
            except HTBError as e:
                logger.warning("IP poll error (attempt %d): %s", attempt + 1, e)
                active_info = {}

            ip = active_info.get("ip")
            spawning = active_info.get("isSpawning", True)

            if ip and not spawning and _IP_RE.match(ip):
                logger.info("Got IP: %s", ip)
                break

            if ip and not _IP_RE.match(ip):
                logger.warning("Invalid IP received: %r", ip)
                ip = None

            logger.info("Waiting for IP... (%d/%d)", attempt + 1, self.SPAWN_MAX_ATTEMPTS)
            time.sleep(self.SPAWN_POLL_INTERVAL)
        else:
            total = self.SPAWN_INITIAL_WAIT + self.SPAWN_MAX_ATTEMPTS * self.SPAWN_POLL_INTERVAL
            raise HTBSpawnError(f"Timeout: no IP for {machine_name} after {total}s")

        return SpawnedMachine(
            name=machine_name,
            machine_id=machine_id,
            ip=ip,
            os=os_name,
            difficulty=difficulty,
        )

    def stop(self, machine_name: str) -> None:
        """Stop a machine by name."""
        machine_id = self._spawned.get(machine_name)
        if machine_id is None:
            machine_id = self.get_machine_info(machine_name)["id"]

        result = self._post("vm/terminate", {"machine_id": machine_id})
        logger.info("Stopped %s: %s", machine_name, result.get("message", result))
        self._spawned.pop(machine_name, None)

    def stop_active(self) -> None:
        """Stop the currently active machine (even if not spawned by this instance)."""
        active = self.active_machine()
        if not active:
            logger.info("No active machines")
            return

        machine_id = active["id"]
        name = active.get("name", str(machine_id))
        result = self._post("vm/terminate", {"machine_id": machine_id})
        logger.info("Stopped %s: %s", name, result.get("message", result))
        self._spawned.clear()

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop all machines spawned by this instance."""
        if exc_type:
            logger.error("Exiting with %s: %s", exc_type.__name__, exc_val)
        for name, machine_id in list(self._spawned.items()):
            try:
                result = self._post("vm/terminate", {"machine_id": machine_id})
                logger.info("Auto-stopped %s: %s", name, result.get("message", result))
            except HTBError as e:
                logger.error("Failed to auto-stop %s: %s", name, e)
        self._spawned.clear()
