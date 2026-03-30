"""Interactive and batch voice approval."""
import json
import re
from pathlib import Path

from scout.db import (
    approve_voice,
    get_db,
    get_pending_voices,
    get_voice_evidence,
    reject_voice,
    skip_voice,
)
from scout.feeds import resolve_feed_url


def interactive_approve(config, topic=None, db_path=None):
    """Present pending voices for interactive approval.

    Returns (approved, rejected, skipped) counts.
    """
    conn = get_db(db_path)
    pending = get_pending_voices(conn, topic)
    nitter_instances = config.get("nitter_instances", [])

    if not pending:
        print("No pending voices to review.")
        conn.close()
        return 0, 0, 0

    total = len(pending)
    approved_count = 0
    rejected_count = 0
    skipped_count = 0
    approved_by_platform = {}
    rejected_by_platform = {}

    # Get existing totals from DB
    for row in conn.execute(
        "SELECT platform, status, COUNT(*) as cnt FROM voices "
        "WHERE status IN ('approved','rejected') GROUP BY platform, status"
    ).fetchall():
        bucket = approved_by_platform if row["status"] == "approved" else rejected_by_platform
        bucket[row["platform"]] = row["cnt"]

    print(f"\n{total} voices pending review:\n")

    for i, voice in enumerate(pending):
        evidence = get_voice_evidence(conn, voice["id"])
        reviewed = approved_count + rejected_count + skipped_count
        remaining = total - reviewed
        print(f"\n  [{reviewed + 1}/{total}]  ({remaining} remaining)")
        _display_candidate(voice, evidence)

        while True:
            choice = input("\n  [a]pprove / [r]eject / [s]kip / [q]uit: ").strip().lower()
            if choice in ("a", "approve"):
                voice_dict = dict(voice)
                feed_url = resolve_feed_url(voice_dict, nitter_instances)
                approve_voice(conn, voice["id"], feed_url)
                approved_count += 1
                p = voice["platform"]
                approved_by_platform[p] = approved_by_platform.get(p, 0) + 1
                print("  -> Approved")
                break
            elif choice in ("r", "reject"):
                reject_voice(conn, voice["id"])
                rejected_count += 1
                p = voice["platform"]
                rejected_by_platform[p] = rejected_by_platform.get(p, 0) + 1
                print("  -> Rejected")
                break
            elif choice in ("s", "skip"):
                skip_voice(conn, voice["id"])
                skipped_count += 1
                print("  -> Skipped (will resurface on next discovery)")
                break
            elif choice in ("q", "quit"):
                print()
                _print_scoreboard(approved_by_platform, rejected_by_platform, approved_count, rejected_count, skipped_count)
                conn.close()
                return approved_count, rejected_count, skipped_count
            else:
                print("  Invalid choice. Enter a/r/s/q.")

        _print_scoreboard(approved_by_platform, rejected_by_platform, approved_count, rejected_count, skipped_count)

    print()
    _print_scoreboard(approved_by_platform, rejected_by_platform, approved_count, rejected_count, skipped_count)
    print("\nAll candidates reviewed!")
    conn.close()
    return approved_count, rejected_count, skipped_count


def batch_approve(config, file_path, db_path=None):
    """Apply approval decisions from a JSON file.

    Expected format:
    [
        {"voice_id": 1, "decision": "approve"},
        {"voice_id": 2, "decision": "reject"},
        ...
    ]
    """
    conn = get_db(db_path)
    nitter_instances = config.get("nitter_instances", [])

    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {path}")
        conn.close()
        return

    with open(path, "r", encoding="utf-8") as f:
        decisions = json.load(f)

    for entry in decisions:
        voice_id = entry["voice_id"]
        decision = entry["decision"].lower()

        voice = conn.execute("SELECT * FROM voices WHERE id=?", (voice_id,)).fetchone()
        if not voice:
            print(f"  Voice {voice_id} not found — skipping")
            continue

        if decision == "approve":
            voice_dict = dict(voice)
            feed_url = resolve_feed_url(voice_dict, nitter_instances)
            approve_voice(conn, voice_id, feed_url)
            print(f"  Approved: {voice['name']} ({voice['platform']})")
        elif decision == "reject":
            reject_voice(conn, voice_id)
            print(f"  Rejected: {voice['name']} ({voice['platform']})")
        elif decision == "skip":
            skip_voice(conn, voice_id)
            print(f"  Skipped: {voice['name']} ({voice['platform']})")

    conn.close()
    print(f"Processed {len(decisions)} decisions from {path}")


def _print_scoreboard(approved_by_platform, rejected_by_platform, session_approved, session_rejected, session_skipped):
    """Print running tally of approvals/rejections by platform."""
    all_platforms = sorted(set(list(approved_by_platform) + list(rejected_by_platform)))
    if not all_platforms:
        return
    print(f"\n  --- Scoreboard (this session: {session_approved} approved, {session_rejected} rejected, {session_skipped} skipped) ---")
    for p in all_platforms:
        a = approved_by_platform.get(p, 0)
        r = rejected_by_platform.get(p, 0)
        bar_a = "+" * a
        bar_r = "-" * r
        print(f"    {p:10s}  {bar_a}{bar_r}  ({a} approved, {r} rejected)")


def _fix_spacing(text):
    """Minimal cleanup for DDG snippet display."""
    # period/comma with no trailing space: "Inc.,a" -> "Inc., a"
    text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)
    return text


def _display_candidate(voice, evidence):
    """Display a candidate voice with evidence for review."""
    print(f"  {'='*60}")
    print(f"  Name:     {voice['name']}")
    print(f"  Platform: {voice['platform']}")
    print(f"  Profile:  {voice['profile_url']}")
    print(f"  Topic:    {voice['topic']}")
    if voice["bio"]:
        print(f"  Bio:")
        for line in voice["bio"].split("\n"):
            print(f"    {line}")
    if evidence:
        print(f"  Articles ({len(evidence)}):")
        for ev in evidence[:5]:
            title = _fix_spacing(ev["title"] or "Untitled")
            print(f"    - {title}")
            print(f"      {ev['url']}")
            if ev["snippet"]:
                short = _fix_spacing(ev["snippet"])[:300].replace("\n", " ")
                if len(ev["snippet"]) > 300:
                    short += "..."
                print(f"      \"{short}\"")
