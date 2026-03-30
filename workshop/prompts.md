# Scout Workshop — Build Your Own Thought Leader Monitor

**Total time: ~4 hours (including breaks)**
**Requirements: A laptop with Python 3.10+ and the free Claude Desktop app (free tier works)**
**Cost to attendees: $0**

You'll use Claude as your coding partner to build a real tool — step by step, prompt by prompt. Each prompt below is self-contained: paste it into Claude Desktop, Claude writes the code, you run it. By the end, you have a working tool you own and take home.

Pick your topic before you start. Replace `[YOUR TOPIC HERE]` everywhere below.

## The Goal

Build a tool that discovers the leading voices on any topic across 5 platforms (Substack, Medium, Reddit, YouTube, Twitter/X), lets you vet them with real evidence (bios, subscriber counts, sample articles), monitors their RSS feeds for new content, and generates weekly digests. Zero cost to run. No paid APIs. No subscriptions. You own it.

## The Stretch Goal

Add AI-powered engagement suggestions — your tool reads what thought leaders are posting and drafts platform-specific responses in your voice. Turns passive monitoring into active participation. (Requires an API key — not covered in the core workshop.)

---

## Prompt 1: Project Setup & Configuration (~20 minutes)

> I want to build a Python CLI tool called "scout" that discovers and monitors thought leaders on any topic. Start by creating the project structure.
>
> Create these files in a `scout/` folder:
>
> 1. `scout/__init__.py` (empty)
> 2. `scout/__main__.py` that imports and calls `main()` from `scout.cli`
> 3. `scout/config.yaml` with this structure:
>    - `topics`: a list where each item has a `name` field. Add one topic: `[YOUR TOPIC HERE]`
>    - `platforms`: list of `substack`, `medium`, `reddit`, `youtube`, `twitter`
>    - `nitter_instances`: list of 3 Nitter instance domains for Twitter RSS (search for current working ones)
>    - `search.delay_seconds`: 2
>    - `search.max_results_per_platform`: 10
>    - `digest.days`: 7
>    - `digest.output_dir`: "digests"
> 4. `scout/config.py` that loads the YAML, merges with sensible defaults, validates that `topics` exists
> 5. `scout/db.py` with SQLite schema for: voices (name, platform, profile_url, handle, topic, status, bio, feed_url), voice_evidence (links found during discovery), content (articles/posts from feeds), discovery_runs, digests. Include helper functions for CRUD operations. Add a migration function that adds missing columns to existing databases.
> 6. `scout/requirements.txt`: ddgs, feedparser, PyYAML
>
> Use `pathlib` for all paths. The DB file should be `scout/scout.db`.

**Check it works:** `python -c "from scout.config import load_config; print(load_config())"`

---

## Prompt 2: Discovery Engine (~45 minutes)

> Now add the discovery engine to my scout tool. Create `scout/discovery.py`.
>
> It should:
> 1. Use `ddgs` (the DuckDuckGo search package) to search for voices. For each platform, scope with site: queries (e.g., `site:substack.com "[YOUR TOPIC HERE]"`)
> 2. Extract candidate authors from search results — parse the URL to find handles (e.g., `username.substack.com` -> handle is "username", `medium.com/@author` -> handle is "author")
> 3. Store each candidate as a "voice" in SQLite with status "pending", plus their evidence links (article titles, URLs, snippets)
> 4. Deduplicate: if the same handle appears in multiple results on the same platform, merge their evidence
> 5. Wait `config.search.delay_seconds` between platform searches to avoid rate limits
> 6. Skip voices that were already discovered (check by profile_url + topic)
> 7. For each NEW candidate, fetch their profile page (profile_url) and extract bio/background info from the page's og:description or meta description tags. For Substack, also extract subscriber count. For YouTube, extract subscriber count and channel description. Store this in the voice's `bio` column.
>
> Then wire it into the CLI: `scout discover "[YOUR TOPIC HERE]"` should search all platforms and report how many candidates were found.
>
> The existing files are: `scout/config.py` (loads config.yaml), `scout/db.py` (SQLite with voices, voice_evidence tables), `scout/cli.py` (argparse entry point).

**Check it works:** `python -m scout discover "[YOUR TOPIC HERE]"` — you should see it search each platform and report candidates found.

---

## Prompt 3: Voice Approval (~30 minutes)

> Add an approval system to scout. Create `scout/approval.py`.
>
> When I run `scout approve`, it should:
> 1. Query all voices with status "pending" from SQLite
> 2. For each one, display: name, platform, profile URL, topic, their bio (if available), and their evidence links (titles + URLs + longer snippet previews, up to 300 chars)
> 3. Show a progress counter like `[3/21] (18 remaining)` before each candidate
> 4. Prompt me to [a]pprove, [r]eject, [s]kip, or [q]uit
> 5. On approve: set status to "approved" and resolve their RSS feed URL (see below)
> 6. On reject: set status to "rejected" (won't resurface)
> 7. On skip: set status to "skipped" (can resurface on next discovery)
> 8. After each decision, show a running scoreboard with approved/rejected counts per platform (including totals from prior sessions). Use `+` and `-` characters as a visual bar.
>
> RSS feed URL resolution rules:
> - Substack: `{handle}.substack.com/feed`
> - Medium: `medium.com/feed/@{handle}`
> - Reddit: `reddit.com/user/{handle}/.rss`
> - YouTube: `youtube.com/feeds/videos.xml?channel_id={id}` (need to fetch the page to find channel ID)
> - Twitter/X: `{nitter_instance}/{handle}/rss` (try instances from config until one works)
>
> Also add `scout approve --from-file decisions.json` for batch processing.
> Also add `scout voices` to list voices by status.
>
> The existing code has `scout/db.py` with `get_pending_voices()`, `approve_voice()`, `reject_voice()`, `skip_voice()`.

**Check it works:** `python -m scout approve` — review your discovered candidates. Approve a few you recognize.

---

## Break (~10 minutes)

Good time to stretch. You now have discovery + approval working!

---

## Prompt 4: RSS Monitoring (~30 minutes)

> Add RSS feed monitoring to scout. Create `scout/monitor.py`.
>
> When I run `scout monitor`, it should:
> 1. Get all approved voices from SQLite
> 2. For each one, fetch their RSS feed URL using `feedparser`
> 3. For each feed entry, check if the URL already exists in the `content` table — skip if so
> 4. Store new entries with: title, URL, published date, summary snippet (truncated to 500 chars)
> 5. Handle feed failures gracefully: log the error, increment a failure counter on the voice, continue to next voice
> 6. For Twitter/X voices: if the current Nitter instance fails, try others from config. Update the stored feed_url if a different instance works.
> 7. Print a summary: "Done: X new items, Y errors"
>
> The existing code has `scout/db.py` with `add_content()` (returns True if new), `increment_feed_failure()`, `reset_feed_failure()`. Feed URLs are stored on each voice record.

**Check it works:** `python -m scout monitor` — you should see it poll each approved voice and report new content found.

---

## Prompt 5: Content Digest (~40 minutes)

> Add digest generation to scout. Create `scout/digest.py`.
>
> When I run `scout digest`, it should:
> 1. Query content from the last N days (default 7, configurable via `--days`)
> 2. Group content by voice (name + platform)
> 3. Generate a markdown file in `scout/digests/digest_YYYY-MM-DD.md`
> 4. Format: header with date, then for each voice a section with article titles as clickable links, dates, and snippet previews
> 5. If no API key, just show titles and links grouped by voice — still fully useful on its own
> 6. Support `--since` / `--until` for custom date ranges
> 7. Support `--list` to show past digests
>
> The existing code has `scout/db.py` with `get_recent_content()`, `log_digest()`, `get_past_digests()`.

**Check it works:** `python -m scout digest` — you should see a digest file appear in `scout/digests/`.

---

## Break (~10 minutes)

You now have a complete discover -> approve -> monitor -> digest pipeline!

---

## Prompt 6: Customize & Extend (~45 minutes)

This one is open-ended. Pick what interests you:

**Option A — Add more topics:**
> Add these topics to my scout config.yaml and run discovery for each:
> - [SECOND TOPIC]
> - [THIRD TOPIC]
> Then run `scout approve` to review the new candidates.

**Option B — Scheduled monitoring:**
> Help me set up a scheduled task so `scout monitor` and `scout digest` run automatically. I'm on [Windows/Mac/Linux]. I want monitoring every 6 hours and a weekly digest on Monday mornings.

**Option C — Better discovery:**
> Improve scout's discovery by adding custom search queries for my topic. Instead of just `site:substack.com "[YOUR TOPIC HERE]"`, add 3-4 more specific queries that would find the real experts. Also add a `--deep` flag that searches for 25 results per platform instead of 10.

**Option D — Export and share:**
> Add a `scout export` command that exports my approved voices and recent content to a clean JSON file I can share with colleagues. Include voice profiles, evidence links, and recent content.

---

## Wrap-Up (~15 minutes)

You built a tool that:
- Searches 5 platforms for experts on any topic
- Lets you vet candidates with real evidence (bios, subscriber counts, sample articles)
- Monitors their RSS feeds for new content
- Generates digests of what the smartest people in your field are publishing
- Costs $0 to run — no paid APIs, no subscriptions

The entire thing lives in one folder. Take it home, add topics, set up scheduled runs, and never miss what the leading voices in your field are writing about.

### What you built would cost you $200+/mo as a SaaS subscription. You built it in 4 hours and you own it.

### Next steps on your own
1. Add more topics to `config.yaml`
2. Run `scout discover` weekly to find new voices
3. Set up scheduled `scout monitor` + `scout digest`
4. **Stretch goal**: Add `scout engage` — AI-powered suggested posts and replies based on what your voices are publishing (requires an API key, ~$0.01/use)
