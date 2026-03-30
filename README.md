# Scout — Thought Leader Discovery & Monitoring

Find and follow the leading voices on any topic. Zero cost. No API keys required.

## Quickstart

```bash
# 1. Install dependencies
pip install -r scout/requirements.txt

# 2. Edit your topics
#    Open scout/config.yaml and change the topic name to whatever interests you

# 3. Discover voices
python -m scout discover

# 4. Review and approve
python -m scout approve

# 5. Monitor for new content
python -m scout monitor

# 6. Generate a digest
python -m scout digest
```

## Commands

| Command | What it does |
|---------|-------------|
| `scout discover "topic"` | Search 5 platforms for voices on a topic |
| `scout discover` | Search all topics from config.yaml |
| `scout approve` | Interactively review discovered voices |
| `scout approve --from-file decisions.json` | Batch approve from JSON |
| `scout monitor` | Poll RSS feeds of approved voices |
| `scout digest` | Generate markdown digest of recent content |
| `scout digest --days 14` | Custom lookback period |
| `scout digest --since 2026-03-01 --until 2026-03-15` | Date range |
| `scout digest --list` | List past digests |
| `scout voices` | List approved voices |
| `scout voices --status pending` | List pending voices |
| `scout config` | Show current configuration |
| `scout config --init` | Create a config.yaml in current directory |

## Configuration

Edit `scout/config.yaml`:

```yaml
topics:
  - name: "your topic here"
    # Optional custom queries:
    # queries:
    #   - "specific search phrase"

platforms:
  - substack
  - medium
  - reddit
  - youtube
  - twitter

search:
  delay_seconds: 2
  max_results_per_platform: 10

digest:
  days: 7
```

## AI Theme Extraction (Optional)

Set `ANTHROPIC_API_KEY` in your environment to enable AI-powered theme summaries in digests. Without it, digests still work — you just get titles and links instead of theme analysis.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# Then install the SDK:
pip install anthropic
```

Cost: ~$0.001 per digest (Claude Haiku).

## Scheduled Monitoring

### Linux/macOS (cron)
```bash
# Poll every 6 hours
0 */6 * * * cd /path/to/project && python -m scout monitor
# Weekly digest on Mondays
0 9 * * 1 cd /path/to/project && python -m scout digest
```

### Windows (Task Scheduler)
Create a basic task that runs:
```
python -m scout monitor
```
Set the trigger to repeat every 6 hours.

## Platforms Searched

- **Substack** — RSS native, best for long-form thought leadership
- **Medium** — Large volume, all topics
- **Reddit** — Every niche, great engagement signals
- **YouTube** — Talks, tutorials, commentary
- **Twitter/X** — Via Nitter RSS (rotates instances automatically)

## Data

All state lives in `scout/scout.db` (SQLite). You can inspect it with any SQLite browser. Digests are saved as markdown in `scout/digests/`.
