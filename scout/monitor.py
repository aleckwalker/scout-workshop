"""RSS feed polling for approved voices."""
import feedparser

from scout.db import (
    add_content,
    get_approved_voices,
    get_db,
    increment_feed_failure,
    reset_feed_failure,
)
from scout.feeds import resolve_feed_url, try_nitter_instances


def poll_all(config, db_path=None):
    """Poll all approved voices for new content.

    Returns (new_count, error_count).
    """
    conn = get_db(db_path)
    voices = get_approved_voices(conn)
    nitter_instances = config.get("nitter_instances", [])

    new_count = 0
    error_count = 0

    for voice in voices:
        feed_url = voice["feed_url"]

        # Resolve feed URL if not set
        if not feed_url:
            voice_dict = dict(voice)
            feed_url = resolve_feed_url(voice_dict, nitter_instances)
            if feed_url:
                conn.execute(
                    "UPDATE voices SET feed_url=? WHERE id=?",
                    (feed_url, voice["id"]),
                )
                conn.commit()

        if not feed_url:
            print(f"  No feed URL for {voice['name']} ({voice['platform']}) — skipping")
            error_count += 1
            continue

        print(f"  Polling {voice['name']} ({voice['platform']})...")
        new, error = _poll_voice(conn, voice, feed_url, nitter_instances)
        new_count += new
        if error:
            error_count += 1

    conn.close()
    return new_count, error_count


def _poll_voice(conn, voice, feed_url, nitter_instances):
    """Poll a single voice's feed. Returns (new_count, had_error)."""
    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            # Feed errored and no entries — try Nitter fallback for Twitter
            if voice["platform"] == "twitter" and voice["handle"]:
                fallback_url, instance = try_nitter_instances(
                    voice["handle"], nitter_instances
                )
                if fallback_url and fallback_url != feed_url:
                    print(f"    Falling back to {instance}...")
                    feed = feedparser.parse(fallback_url)
                    # Update stored feed URL to working instance
                    conn.execute(
                        "UPDATE voices SET feed_url=? WHERE id=?",
                        (fallback_url, voice["id"]),
                    )
                    conn.commit()

        if feed.bozo and not feed.entries:
            print(f"    Feed error: {feed.bozo_exception}")
            increment_feed_failure(conn, voice["id"])
            return 0, True

        new_count = 0
        for entry in feed.entries:
            title = entry.get("title", "Untitled")
            url = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            summary = entry.get("summary", "")

            # Truncate summary
            if len(summary) > 500:
                summary = summary[:497] + "..."

            if url and add_content(conn, voice["id"], title, url, published, summary):
                new_count += 1

        if new_count:
            print(f"    {new_count} new entries")

        reset_feed_failure(conn, voice["id"])
        return new_count, False

    except Exception as e:
        print(f"    Error polling {voice['name']}: {e}")
        increment_feed_failure(conn, voice["id"])
        return 0, True
