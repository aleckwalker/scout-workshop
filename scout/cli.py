"""Scout CLI — discover and monitor thought leaders on any topic."""
import argparse
import sys

from scout.config import load_config, get_topic_names


def main():
    parser = argparse.ArgumentParser(
        prog="scout",
        description="Discover and monitor thought leaders on any topic.",
    )
    parser.add_argument(
        "--config", "-c", default=None, help="Path to config.yaml"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # discover
    p_discover = subparsers.add_parser("discover", help="Find voices on a topic")
    p_discover.add_argument("topic", nargs="?", help="Topic to search (or all from config)")

    # approve
    p_approve = subparsers.add_parser("approve", help="Review and approve discovered voices")
    p_approve.add_argument("--topic", "-t", help="Filter by topic")
    p_approve.add_argument("--from-file", help="Batch approve from JSON file")

    # monitor
    p_monitor = subparsers.add_parser("monitor", help="Poll RSS feeds of approved voices")

    # digest
    p_digest = subparsers.add_parser("digest", help="Generate content digest")
    p_digest.add_argument("--days", "-d", type=int, help="Lookback days (default from config)")
    p_digest.add_argument("--since", help="Start date (YYYY-MM-DD)")
    p_digest.add_argument("--until", help="End date (YYYY-MM-DD)")
    p_digest.add_argument("--list", action="store_true", help="List past digests")

    # config
    p_config = subparsers.add_parser("config", help="Show or validate configuration")
    p_config.add_argument("--init", action="store_true", help="Create default config")
    p_config.add_argument("--validate", action="store_true", help="Validate config")

    # voices
    p_voices = subparsers.add_parser("voices", help="List tracked voices")
    p_voices.add_argument("--status", "-s", choices=["approved", "pending", "rejected", "all"], default="approved")
    p_voices.add_argument("--topic", "-t", help="Filter by topic")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "config" and args.init:
        _cmd_config_init()
        return

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Config error: {e}")
        sys.exit(1)

    commands = {
        "discover": _cmd_discover,
        "approve": _cmd_approve,
        "monitor": _cmd_monitor,
        "digest": _cmd_digest,
        "config": _cmd_config,
        "voices": _cmd_voices,
    }
    commands[args.command](config, args)


def _cmd_discover(config, args):
    from scout.discovery import discover_topic

    topics = [args.topic] if args.topic else get_topic_names(config)

    for topic in topics:
        print(f"\nDiscovering voices for: {topic}")
        results = discover_topic(config, topic)
        new_count = sum(1 for _, is_new in results if is_new)
        print(f"  Found {len(results)} candidates ({new_count} new)")

    print(f"\nRun 'scout approve' to review candidates.")


def _cmd_approve(config, args):
    from scout.approval import batch_approve, interactive_approve

    if args.from_file:
        batch_approve(config, args.from_file)
    else:
        interactive_approve(config, topic=args.topic)


def _cmd_monitor(config, args):
    from scout.monitor import poll_all

    print("Polling approved voices...")
    new_count, error_count = poll_all(config)
    print(f"\nDone: {new_count} new items, {error_count} errors")

    if new_count:
        print("Run 'scout digest' to generate a summary.")


def _cmd_digest(config, args):
    from scout.digest import generate_digest, list_digests

    if args.list:
        digests = list_digests()
        if not digests:
            print("No past digests.")
            return
        print("Past digests:")
        for d in digests:
            ai = " (with AI themes)" if d["has_ai_themes"] else ""
            print(f"  {d['created_at']} — {d['content_count']} items{ai}")
            print(f"    {d['file_path']}")
        return

    generate_digest(config, days=args.days, since=args.since, until=args.until)


def _cmd_config(config, args):
    if args.validate:
        print("Config is valid.")
    print(f"Config loaded from: {config['_config_path']}")
    print(f"Topics: {', '.join(get_topic_names(config))}")
    print(f"Platforms: {', '.join(config['platforms'])}")
    print(f"Nitter instances: {', '.join(config.get('nitter_instances', []))}")
    print(f"AI themes: {'enabled' if config.get('anthropic_api_key') else 'disabled (no API key)'}")


def _cmd_config_init():
    import shutil
    from pathlib import Path

    src = Path(__file__).parent / "config.yaml"
    dst = Path.cwd() / "config.yaml"
    if dst.exists():
        print(f"Config already exists at {dst}")
        return
    shutil.copy(src, dst)
    print(f"Created config at {dst} — edit topics and run 'scout discover'")


def _cmd_voices(config, args):
    from scout.db import get_db

    conn = get_db()
    status_filter = args.status

    query = "SELECT * FROM voices"
    params = []
    conditions = []

    if status_filter != "all":
        conditions.append("status=?")
        params.append(status_filter)
    if args.topic:
        conditions.append("topic=?")
        params.append(args.topic)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY topic, name"

    voices = conn.execute(query, params).fetchall()
    conn.close()

    if not voices:
        print(f"No {status_filter} voices found.")
        return

    current_topic = None
    for v in voices:
        if v["topic"] != current_topic:
            current_topic = v["topic"]
            print(f"\n  [{current_topic}]")
        status_badge = {"approved": "+", "pending": "?", "rejected": "x", "skipped": "-"}
        badge = status_badge.get(v["status"], " ")
        print(f"    [{badge}] {v['name']} ({v['platform']}) — {v['profile_url']}")
