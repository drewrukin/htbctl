# htbctl

Python library and CLI for HackTheBox machine lifecycle automation.

```
spawn → wait for IP → attack → stop
```

Requires Python 3.9+. Works with free and VIP HTB accounts.

---

## Install

```bash
pip install htbctl
```

## Setup

1. Go to https://app.hackthebox.com/account-settings → **API Tokens** → **Add New Token**
2. Save the token in any of these locations (checked in order):

```bash
# Option A — dedicated config (recommended)
mkdir -p ~/.config/htbctl
echo "HTB_TOKEN=eyJ..." > ~/.config/htbctl/.env

# Option B — .env in current directory
echo "HTB_TOKEN=eyJ..." > .env

# Option C — environment variable
export HTB_TOKEN=eyJ...
```

Or pass the token directly in Python:
```python
htb = HTBIntegration(token="eyJ...")
htb = HTBIntegration(env_path="path/to/.env")
```

3. Make sure HTB VPN is connected — spawned machines are only reachable through VPN.

---

## Python API

```python
from htbctl import HTBIntegration

# Reads: ~/.config/htbctl/.env → .env → HTB_TOKEN env var
with HTBIntegration() as htb:
    machine = htb.spawn("Cap")
    print(machine.ip)   # 10.10.11.xx
    # ... run your exploit here ...
# machine is stopped automatically
```

Explicit token:
```python
htb = HTBIntegration(token="eyJ...")
machine = htb.spawn("Precious")
htb.stop("Precious")
```

---

## CLI

```bash
htbctl login                        # verify token
htbctl list                         # list all retired machines
htbctl list cap                     # filter by name

htbctl spawn Precious               # spawn a machine, print IP
htbctl spawn Precious --force       # stop active machine first, then spawn

htbctl stop Precious                # stop by name
htbctl stop --active                # stop whatever is running
```

---

## SpawnedMachine

```python
machine = htb.spawn("Cap")
machine.name        # "Cap"
machine.ip          # "10.10.11.xx"
machine.os          # "Linux"
machine.difficulty  # "Easy"
machine.machine_id  # 351
```

---

## Exceptions

```python
from htbctl import HTBError, HTBAuthError, HTBMachineNotFoundError, HTBSpawnError, HTBRateLimitError
```

| Exception | When |
|-----------|------|
| `HTBAuthError` | Invalid or expired token |
| `HTBMachineNotFoundError` | Machine name not found |
| `HTBSpawnError` | Spawn failed or IP timeout |
| `HTBRateLimitError` | API rate limit (HTTP 429) |
| `HTBError` | Base class for everything above |

---

## Logging

The library is silent by default. To see what's happening:

```python
import logging
logging.getLogger("htbctl").addHandler(logging.StreamHandler())
logging.getLogger("htbctl").setLevel(logging.DEBUG)
```

The CLI enables logging automatically with `[htbctl]` prefix.

---

## Credits & Alternatives

This project was inspired by [pyhackthebox](https://github.com/clubby789/htb-api) by @clubby789.

**Why htbctl exists:**
- `pyhackthebox` is a general-purpose client (last update: 2022)
- `htbctl` is focused on automation: spawn → attack → stop
- App Token auth only (no email/password/OTP)
- Context manager with auto-stop

If you need full HTB API coverage (challenges, leaderboards, user profiles) — use `pyhackthebox`.
If you need to automate machine attacks — use `htbctl`.
