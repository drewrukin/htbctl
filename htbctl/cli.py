"""htbctl CLI — HackTheBox machine management."""

import argparse
import logging
import sys

from .client import HTBIntegration
from .exceptions import HTBError


def _setup_logging():
    """Configure logging so library messages appear as clean CLI output."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[htbctl] %(message)s"))
    logging.getLogger("htbctl").addHandler(handler)
    logging.getLogger("htbctl").setLevel(logging.INFO)


def cmd_login(args):
    info = HTBIntegration().login()
    print(f"Logged in: {info.get('name')} | VIP: {info.get('isVip')} | VIP+: {info.get('isVipPlus')}")


def cmd_list(args):
    machines = HTBIntegration().list_available(query=args.query or "")
    print(f"\n{'='*55}")
    print(f"{'ID':<6} {'Machine':<20} {'OS':<10} {'Difficulty'}")
    print(f"{'='*55}")
    for m in machines:
        print(f"{m.get('id'):<6} {m.get('name'):<20} {m.get('os',''):<10} {m.get('difficultyText','')}")
    print(f"{'='*55}")
    print(f"Total: {len(machines)}\n")


def cmd_spawn(args):
    htb = HTBIntegration()
    if args.force:
        htb.stop_active()
    machine = htb.spawn(args.name)
    print(f"\nMachine : {machine.name}")
    print(f"IP      : {machine.ip}")
    print(f"OS      : {machine.os}")
    print(f"Diff    : {machine.difficulty}")
    print(f"\nTo stop: htbctl stop {machine.name}")


def cmd_stop(args):
    htb = HTBIntegration()
    if args.active:
        htb.stop_active()
    elif args.name:
        htb.stop(args.name)
    else:
        print("Specify a machine name or --active")
        sys.exit(1)


def main():
    _setup_logging()

    parser = argparse.ArgumentParser(
        description="htbctl — HackTheBox machine management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  htbctl login\n"
            "  htbctl list\n"
            "  htbctl list cap\n"
            "  htbctl spawn Precious\n"
            "  htbctl spawn Precious --force\n"
            "  htbctl stop Precious\n"
            "  htbctl stop --active\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("login", help="Verify authentication").set_defaults(func=cmd_login)

    p = sub.add_parser("list", help="List retired machines")
    p.add_argument("query", nargs="?", default="", help="Filter by name")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("spawn", help="Spawn a machine")
    p.add_argument("name", help="Machine name")
    p.add_argument("--force", action="store_true", help="Stop active machine before spawning")
    p.set_defaults(func=cmd_spawn)

    p = sub.add_parser("stop", help="Stop a machine")
    p.add_argument("name", nargs="?", help="Machine name")
    p.add_argument("--active", action="store_true", help="Stop the currently active machine")
    p.set_defaults(func=cmd_stop)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except HTBError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
