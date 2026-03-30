"""Content digest generation with optional AI theme extraction."""
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from scout.db import get_db, get_past_digests, get_recent_content, log_digest


def generate_digest(config, days=None, since=None, until=None, db_path=None):
    """Generate a markdown digest of recent content.

    Returns the file path of the generated digest, or None if no content.
    """
    conn = get_db(db_path)
    days = days or config["digest"]["days"]

    content = get_recent_content(conn, days=days, since=since, until=until)
    if not content:
        print("No new content found for digest.")
        conn.close()
        return None

    # Group by voice
    by_voice = defaultdict(list)
    for row in content:
        key = f"{row['voice_name']} ({row['platform']})"
        by_voice[key].append(row)

    # Build markdown
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# Scout Digest — {date_str}", ""]

    # Optional AI themes
    api_key = config.get("anthropic_api_key")
    has_themes = False
    if api_key:
        themes = _extract_themes(content, api_key)
        if themes:
            has_themes = True
            lines.append("## Key Themes")
            lines.append("")
            lines.append(themes)
            lines.append("")

    lines.append(f"## Content ({len(content)} items from {len(by_voice)} voices)")
    lines.append("")

    for voice_label, items in sorted(by_voice.items()):
        lines.append(f"### {voice_label}")
        lines.append("")
        for item in items:
            pub_date = item["published_at"] or "unknown date"
            lines.append(f"- [{item['title']}]({item['url']}) — {pub_date}")
            if item["summary"]:
                # First 150 chars of summary
                short = item["summary"][:150].replace("\n", " ")
                if len(item["summary"]) > 150:
                    short += "..."
                lines.append(f"  > {short}")
        lines.append("")

    # Write to file
    output_dir = Path(config["digest"]["output_dir"])
    if not output_dir.is_absolute():
        output_dir = Path(__file__).parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"digest_{date_str}.md"
    file_path.write_text("\n".join(lines), encoding="utf-8")

    log_digest(conn, str(file_path), len(content), has_themes)
    conn.close()

    print(f"Digest written to {file_path} ({len(content)} items)")
    return file_path


def list_digests(db_path=None):
    """List all past digests."""
    conn = get_db(db_path)
    digests = get_past_digests(conn)
    conn.close()
    return digests


def _extract_themes(content, api_key):
    """Use Claude Haiku to extract themes from content. Returns markdown string or None."""
    try:
        import anthropic
    except ImportError:
        print("  (anthropic package not installed — skipping AI themes)")
        return None

    # Build content summary for the prompt
    content_lines = []
    for item in content[:50]:  # Cap to control cost
        content_lines.append(f"- {item['voice_name']}: \"{item['title']}\"")
        if item["summary"]:
            content_lines.append(f"  Summary: {item['summary'][:200]}")

    content_text = "\n".join(content_lines)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Below are recent articles/posts from thought leaders I follow. "
                        "Identify 3-5 key themes or trends across these posts. "
                        "Be concise — one sentence per theme. Format as a bullet list.\n\n"
                        f"{content_text}"
                    ),
                }
            ],
        )
        result = response.content[0].text

        # Log cost estimate
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (input_tokens * 0.80 + output_tokens * 4.00) / 1_000_000
        print(f"  AI themes: {input_tokens} in / {output_tokens} out (~${cost:.4f})")

        return result

    except Exception as e:
        print(f"  AI theme extraction failed: {e}")
        return None
