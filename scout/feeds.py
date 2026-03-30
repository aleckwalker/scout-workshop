"""RSS feed URL resolution and Nitter instance management."""
import re
import urllib.request


def resolve_feed_url(voice, nitter_instances=None):
    """Resolve the RSS feed URL for a voice based on platform and profile."""
    platform = voice["platform"] if isinstance(voice, dict) else voice.platform
    profile = voice["profile_url"] if isinstance(voice, dict) else voice.profile_url
    handle = voice["handle"] if isinstance(voice, dict) else voice.handle

    resolvers = {
        "substack": _resolve_substack,
        "medium": _resolve_medium,
        "reddit": _resolve_reddit,
        "youtube": _resolve_youtube,
        "twitter": _resolve_twitter,
    }

    resolver = resolvers.get(platform)
    if not resolver:
        return None

    if platform == "twitter":
        return resolver(handle, profile, nitter_instances or [])
    return resolver(handle, profile)


def _resolve_substack(handle, profile_url):
    """Substack: <publication>.substack.com/feed"""
    match = re.search(r"https?://([^.]+)\.substack\.com", profile_url)
    if match:
        return f"https://{match.group(1)}.substack.com/feed"
    return f"{profile_url.rstrip('/')}/feed"


def _resolve_medium(handle, profile_url):
    """Medium: medium.com/feed/@username"""
    if handle:
        clean = handle.lstrip("@")
        return f"https://medium.com/feed/@{clean}"
    match = re.search(r"medium\.com/@([^/?]+)", profile_url)
    if match:
        return f"https://medium.com/feed/@{match.group(1)}"
    return None


def _resolve_reddit(handle, profile_url):
    """Reddit: reddit.com/user/username/.rss or /r/subreddit/.rss"""
    if "/r/" in profile_url:
        match = re.search(r"/r/([^/?]+)", profile_url)
        if match:
            return f"https://www.reddit.com/r/{match.group(1)}/.rss"
    if handle:
        return f"https://www.reddit.com/user/{handle}/.rss"
    return None


def _resolve_youtube(handle, profile_url):
    """YouTube: RSS feed by channel ID. Requires a lookup if we only have a handle."""
    # If we have a channel ID already
    match = re.search(r"channel/([^/?]+)", profile_url)
    if match:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={match.group(1)}"

    # Try to extract channel ID from page
    channel_id = _lookup_youtube_channel_id(profile_url)
    if channel_id:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    return None


def _lookup_youtube_channel_id(url):
    """Fetch a YouTube page and extract the channel ID from meta tags."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        match = re.search(r'"channelId"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'<meta\s+itemprop="channelId"\s+content="([^"]+)"', html)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _resolve_twitter(handle, profile_url, nitter_instances):
    """Twitter/X: try Nitter instances in order."""
    if not handle:
        match = re.search(r"(?:x|twitter)\.com/([^/?]+)", profile_url)
        if match:
            handle = match.group(1)
    if not handle:
        return None

    for instance in nitter_instances:
        feed_url = f"https://{instance}/{handle}/rss"
        if _check_feed(feed_url):
            return feed_url

    # Return first instance even if check failed — monitor will handle retries
    if nitter_instances:
        return f"https://{nitter_instances[0]}/{handle}/rss"
    return None


def _check_feed(url):
    """Quick check if a feed URL responds."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def try_nitter_instances(handle, nitter_instances):
    """Try each Nitter instance until one works. Returns (feed_url, instance) or (None, None)."""
    for instance in nitter_instances:
        feed_url = f"https://{instance}/{handle}/rss"
        if _check_feed(feed_url):
            return feed_url, instance
    return None, None
