"""Configuration loading and validation for Scout."""
import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"

DEFAULTS = {
    "platforms": ["substack", "medium", "reddit", "youtube", "twitter"],
    "nitter_instances": [
        "nitter.privacydev.net",
        "nitter.poast.org",
        "nitter.woodland.cafe",
    ],
    "search": {
        "delay_seconds": 2,
        "max_results_per_platform": 10,
    },
    "monitor": {
        "interval_hours": 6,
    },
    "digest": {
        "days": 7,
        "output_dir": "digests",
    },
}

REQUIRED_FIELDS = ["topics"]


def load_config(config_path=None):
    """Load config from YAML, merge with defaults, validate."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Config not found: {path}\nRun 'scout config --init' to create one."
        )

    with open(path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    config = _merge_defaults(user_config)
    _validate(config)

    # Check for API key in config or environment
    config["anthropic_api_key"] = (
        config.get("anthropic_api_key")
        or os.environ.get("ANTHROPIC_API_KEY")
    )

    config["_config_path"] = str(path)
    return config


def _merge_defaults(user_config):
    """Deep merge user config over defaults."""
    merged = dict(DEFAULTS)
    for key, value in user_config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _validate(config):
    """Validate required fields exist."""
    for field in REQUIRED_FIELDS:
        if field not in config or not config[field]:
            raise ValueError(
                f"Missing required config field: '{field}'\n"
                f"Add at least one topic to config.yaml."
            )

    for topic in config["topics"]:
        if not isinstance(topic, dict) or "name" not in topic:
            raise ValueError(
                f"Each topic must have a 'name' field. Got: {topic}"
            )


def get_topic_names(config):
    """Extract topic name strings from config."""
    return [t["name"] for t in config["topics"]]


def get_topic_queries(config, topic_name):
    """Get custom queries for a topic, or None to use auto-generated ones."""
    for topic in config["topics"]:
        if topic["name"] == topic_name:
            return topic.get("queries")
    return None
