"""Topic-driven voice discovery across platforms using DuckDuckGo."""
import html
import re
import time
import urllib.request
from difflib import SequenceMatcher

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from scout.config import get_topic_queries
from scout.db import (
    add_evidence,
    get_db,
    log_discovery_run,
    update_voice_bio,
    upsert_voice,
)

# Site-scope patterns for DuckDuckGo
PLATFORM_SITES = {
    "substack": "site:substack.com",
    "medium": "site:medium.com",
    "reddit": "site:reddit.com",
    "youtube": "site:youtube.com",
    "twitter": "site:x.com OR site:twitter.com",
}

# Patterns to extract author/handle from URLs
AUTHOR_PATTERNS = {
    "substack": re.compile(r"https?://([^.]+)\.substack\.com"),
    "medium": re.compile(r"medium\.com/@([^/?]+)"),
    "reddit": re.compile(r"reddit\.com/(?:user|u)/([^/?]+)"),
    "youtube": re.compile(r"youtube\.com/(?:@|channel/|c/)([^/?]+)"),
    "twitter": re.compile(r"(?:x|twitter)\.com/([^/?]+)"),
}


def discover_topic(config, topic_name, db_path=None):
    """Run discovery for a single topic across all configured platforms.

    Returns list of (voice_id, is_new) tuples.
    """
    conn = get_db(db_path)
    platforms = config.get("platforms", list(PLATFORM_SITES.keys()))
    delay = config["search"]["delay_seconds"]
    max_results = config["search"]["max_results_per_platform"]
    custom_queries = get_topic_queries(config, topic_name)

    all_candidates = []

    for platform in platforms:
        if platform not in PLATFORM_SITES:
            print(f"  Skipping unknown platform: {platform}")
            continue

        print(f"  Searching {platform}...")
        results = _search_platform(
            topic_name, platform, max_results, custom_queries
        )
        log_discovery_run(conn, topic_name, platform, len(results))

        for result in results:
            candidate = _extract_candidate(result, platform)
            if candidate:
                all_candidates.append(candidate)

        time.sleep(delay)

    # Deduplicate across platforms
    merged = _deduplicate(all_candidates)

    # Store in database
    voice_results = []
    for candidate in merged:
        voice_id, is_new = upsert_voice(
            conn,
            candidate["name"],
            candidate["platform"],
            candidate["profile_url"],
            candidate["handle"],
            topic_name,
        )
        for evidence in candidate["evidence"]:
            add_evidence(
                conn, voice_id, evidence["title"], evidence["url"], evidence["snippet"]
            )
        # Fetch bio for new voices
        if is_new:
            bio = _fetch_profile_bio(candidate["profile_url"], candidate["platform"])
            if bio:
                update_voice_bio(conn, voice_id, bio)
        voice_results.append((voice_id, is_new))

    conn.close()
    return voice_results


def _search_platform(topic, platform, max_results, custom_queries=None):
    """Search a single platform via DuckDuckGo."""
    site_scope = PLATFORM_SITES[platform]

    if custom_queries:
        queries = [f"{site_scope} {q}" for q in custom_queries]
    else:
        queries = [f'{site_scope} "{topic}"']

    all_results = []
    with DDGS() as ddgs:
        for query in queries:
            try:
                results = list(ddgs.text(query, max_results=max_results))
                all_results.extend(results)
            except Exception as e:
                print(f"    Search error for '{query}': {e}")

    return all_results


def _extract_candidate(result, platform):
    """Extract a candidate voice from a search result."""
    url = result.get("href", result.get("link", ""))
    title = result.get("title", "")
    snippet = result.get("body", result.get("snippet", ""))

    if not url:
        return None

    # Try to extract author/handle from URL
    handle = None
    pattern = AUTHOR_PATTERNS.get(platform)
    if pattern:
        match = pattern.search(url)
        if match:
            handle = match.group(1)

    # Derive a name from the handle or title
    name = _derive_name(handle, title, platform)
    if not name:
        return None

    # Build profile URL
    profile_url = _build_profile_url(handle, url, platform)

    return {
        "name": name,
        "handle": handle,
        "platform": platform,
        "profile_url": profile_url,
        "evidence": [{"title": title, "url": url, "snippet": snippet}],
    }


def _derive_name(handle, title, platform):
    """Best-effort name derivation from handle or title."""
    if handle:
        # Clean up handle into readable name
        clean = handle.replace("-", " ").replace("_", " ")
        # Skip generic handles
        if clean.lower() in ("www", "blog", "the", "official", "comments", "r"):
            return None
        return clean.title()

    # Fallback: try to extract from title (e.g., "Author Name - Article Title")
    if " - " in title:
        parts = title.split(" - ")
        return parts[0].strip() if len(parts[0]) < 40 else None
    if " | " in title:
        parts = title.split(" | ")
        return parts[-1].strip() if len(parts[-1]) < 40 else None

    return None


def _build_profile_url(handle, content_url, platform):
    """Build a profile URL from handle, falling back to the content URL."""
    if not handle:
        return content_url

    profile_urls = {
        "substack": f"https://{handle}.substack.com",
        "medium": f"https://medium.com/@{handle}",
        "reddit": f"https://reddit.com/user/{handle}",
        "youtube": f"https://youtube.com/@{handle}",
        "twitter": f"https://x.com/{handle}",
    }
    return profile_urls.get(platform, content_url)


def _deduplicate(candidates):
    """Merge candidates that appear to be the same person across platforms."""
    if not candidates:
        return []

    merged = []
    used = set()

    for i, cand in enumerate(candidates):
        if i in used:
            continue

        group = dict(cand)  # copy
        group["evidence"] = list(cand["evidence"])

        for j in range(i + 1, len(candidates)):
            if j in used:
                continue
            other = candidates[j]

            # Same handle on same platform — merge evidence
            if (
                cand["platform"] == other["platform"]
                and cand["handle"]
                and cand["handle"] == other["handle"]
            ):
                group["evidence"].extend(other["evidence"])
                used.add(j)
            # Different platforms, similar name — note but keep separate DB entries
            elif _similar_names(cand["name"], other["name"]):
                # For now, just deduplicate evidence on the same platform
                if cand["platform"] == other["platform"]:
                    group["evidence"].extend(other["evidence"])
                    used.add(j)

        # Deduplicate evidence by URL
        seen_urls = set()
        unique_evidence = []
        for ev in group["evidence"]:
            if ev["url"] not in seen_urls:
                seen_urls.add(ev["url"])
                unique_evidence.append(ev)
        group["evidence"] = unique_evidence[:5]  # Cap at 5

        merged.append(group)
        used.add(i)

    return merged


def _similar_names(name1, name2):
    """Check if two names are similar enough to be the same person."""
    if not name1 or not name2:
        return False
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio() > 0.8


def _fetch_profile_bio(profile_url, platform):
    """Fetch the profile page and extract bio/description metadata."""
    try:
        req = urllib.request.Request(
            profile_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            page = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    bio_parts = []

    # 1. og:description or meta description — usually has the person's bio
    desc = _extract_meta(page, "og:description") or _extract_meta(page, "description")
    if desc:
        bio_parts.append(desc)

    # 2. Platform-specific extraction
    if platform == "substack":
        # Substack profile pages have a "about" blurb and subscriber count
        sub_count = re.search(r'(\d[\d,]+)\s*subscriber', page, re.IGNORECASE)
        if sub_count:
            bio_parts.append(f"Subscribers: {sub_count.group(1)}")
        # Author name from og:title or page title
        author = _extract_meta(page, "og:title")
        if author and author not in " ".join(bio_parts):
            bio_parts.insert(0, f"Publication: {author}")

    elif platform == "medium":
        # Medium profiles sometimes have follower counts
        followers = re.search(r'(\d[\d,.]*[KkMm]?)\s*[Ff]ollower', page)
        if followers:
            bio_parts.append(f"Followers: {followers.group(1)}")

    elif platform == "youtube":
        # YouTube channels: subscriber count, channel description
        subs = re.search(r'"subscriberCountText":\s*\{"simpleText":\s*"([^"]+)"', page)
        if subs:
            bio_parts.append(f"Subscribers: {subs.group(1)}")
        chan_desc = re.search(r'"description":\s*"([^"]{10,300})"', page)
        if chan_desc and chan_desc.group(1) not in " ".join(bio_parts):
            bio_parts.append(chan_desc.group(1).replace("\\n", " "))

    elif platform == "twitter":
        # Nitter/X profiles: bio from meta
        pass  # og:description usually covers it

    elif platform == "reddit":
        # Reddit user/subreddit description
        pass  # og:description usually covers it

    if not bio_parts:
        return None

    return "\n".join(bio_parts)


def _extract_meta(html_str, name):
    """Extract content from a meta tag by name or property."""
    # Try property= first (og: tags), then name=
    for attr in ("property", "name"):
        pattern = rf'<meta\s+{attr}="{re.escape(name)}"\s+content="([^"]*)"'
        match = re.search(pattern, html_str, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
        # Also try reversed attribute order
        pattern = rf'<meta\s+content="([^"]*)"\s+{attr}="{re.escape(name)}"'
        match = re.search(pattern, html_str, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return None
