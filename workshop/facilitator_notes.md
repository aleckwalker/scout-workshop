# Facilitator Notes — Scout Workshop

## Framing

**The Goal:** Build a tool that discovers the leading voices on any topic across 5 platforms, lets you vet them with real evidence, monitors their RSS feeds, and generates weekly digests. Zero cost. You own it. You take it home.

**The Stretch Goal:** Add AI-powered engagement suggestions — your tool reads what thought leaders are posting and drafts platform-specific responses in your voice. (Requires API key, not covered in core workshop.)

## Timing Guide

| Section | Duration | Cumulative |
|---------|----------|-----------|
| Prompt 1: Project Setup | 20 min | 0:20 |
| Prompt 2: Discovery Engine | 45 min | 1:05 |
| Prompt 3: Voice Approval | 30 min | 1:35 |
| Break | 10 min | 1:45 |
| Prompt 4: RSS Monitoring | 30 min | 2:15 |
| Prompt 5: Content Digest | 40 min | 2:55 |
| Break | 10 min | 3:05 |
| Prompt 6: Customize | 45 min | 3:50 |
| Wrap-Up | 10 min | 4:00 |

## Pre-Workshop Checklist

- [ ] Attendees have Python 3.10+ installed
- [ ] Attendees have Claude Desktop installed (free tier works)
- [ ] Test DuckDuckGo search from the venue (some corporate networks block it)
- [ ] Have 3-5 backup Nitter instances ready (check the day before)
- [ ] Prepare a sample topic for live demo
- [ ] Have the completed `scout/` repo ready as a fallback (see below)

## Free Tier Claude Desktop — Will It Be Enough?

**Yes.** The workshop needs roughly 8-18 messages total across 6 prompts. Free tier currently gives ~25 messages per 5 hours on Sonnet. Fits comfortably for attendees who paste clean prompts.

**If someone runs out of messages:**
1. They can copy files directly from the fallback repo and keep following along
2. Pair them with someone who still has messages
3. They can finish on their own after the rate limit resets

**Recommendation:** Have the completed tool available as a GitHub repo or zip file. Attendees who hit limits copy the files they need and continue with the next prompt. Nobody gets stuck.

## Distribution

Two options for giving attendees the finished tool:
1. **Public GitHub repo** (e.g., `scout-workshop`) — they fork/clone. Best for updates.
2. **Zip file** — USB or download link. No GitHub account needed.

The `scout/` folder is fully self-contained. No external accounts, no cloud services, no API keys required for the core tool.

## Common Issues & Fixes

### "ModuleNotFoundError: No module named 'ddgs'"
Attendee forgot `pip install -r requirements.txt`. Or they have multiple Python versions — make sure they use the right pip.

### DuckDuckGo rate limiting
If many attendees search simultaneously, DDG may throttle. Fix: increase `delay_seconds` to 3-5, or stagger starts (have tables start 2 min apart).

### "0 candidates found"
Usually means the search returned results but URL patterns didn't match. Check that the topic produces results on the target platforms. Try broader search terms.

### Nitter instances down
This happens. Explain that it's a feature, not a bug — the code tries multiple instances. If ALL are down:
1. Remove `twitter` from `platforms` in config.yaml
2. Explain this is why the tool has fallback design
3. Good teaching moment about building resilient systems

### YouTube RSS not working
YouTube feeds require the channel ID, which requires fetching the page. If this is slow or fails, skip YouTube for the workshop and show it working later.

### Windows path issues
Some attendees may see path errors. Ensure all code uses `pathlib.Path`, not string concatenation. The tool is tested on Windows.

## Teaching Points

### Prompt 1 — "Why YAML?"
Most readable config format for non-developers. Compare to JSON (needs quotes everywhere) and TOML (less familiar). Workshop attendees edit this by hand.

### Prompt 2 — "Why DuckDuckGo?"
No API key, no billing, no signup. Google Custom Search is better but requires a credit card. The goal is zero friction.

### Prompt 3 — "Human in the loop"
The tool never auto-adds voices. This is a design choice: AI is good at finding, humans are good at judging credibility. Present the evidence, let the human decide.

### Prompt 4 — "RSS is the original API"
It's been around since 1999. Most platforms still support it. No auth, no rate limits, no deprecation notices. Building on RSS means your tool works even if the platform changes their API.

### Prompt 5 — "Build useful first, add AI second"
The digest works without any API key. AI theme extraction is an enhancement, not a requirement. This is the right pattern: build something useful first, then add AI to make it better. Not the other way around.

### The $200/mo line
Media monitoring SaaS tools (Mention, Brand24, Meltwater) charge $200-1000/mo for similar functionality. The attendees just built their own in 4 hours for free. That's the punchline.

## If You Run Out of Time

**Minimum viable workshop (2 hours):** Prompts 1-3 only. Attendees leave with discovery + approval working. They can add monitoring and digest on their own.

**Comfortable pace (3 hours):** Prompts 1-5. Full pipeline working. Skip Prompt 6.

**Full workshop (4 hours):** All 6 prompts including customization.

## Sample Demo Script

1. "Let me show you what we're building" — run discover, approve 2-3 voices, monitor, digest
2. "Now you're going to build this yourself, with Claude as your coding partner"
3. "Open Claude and paste Prompt 1. Replace the topic with whatever interests you."
4. Walk the room, help people who get stuck
5. At each checkpoint ("Check it works"), make sure everyone has it running before moving on
