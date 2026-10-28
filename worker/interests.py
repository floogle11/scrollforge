"""Shared interests stored in an owner-authored GitHub configuration issue."""
import json
import os
from pathlib import Path

TITLE = "ScrollForge current interests"
KIND = "scrollforge-interests-v1"
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs/data/interests.json"


def validate_interests(value):
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError("Use at most 12 interests")
    result = []
    for item in value:
        if not isinstance(item, str) or not 1 <= len(item.strip()) <= 160:
            raise ValueError("Each interest needs 1–160 characters")
        if item.strip().casefold() not in {s.casefold() for s in result}:
            result.append(item.strip())
    return result


def load_interests(repository=None, token=None):
    repository = repository or os.getenv("GITHUB_REPOSITORY")
    token = token or os.getenv("GITHUB_TOKEN")
    defaults = validate_interests(json.loads(DEFAULT_PATH.read_text(encoding="utf-8")))
    if not repository or not token:
        return defaults
    import requests
    # Owner-only configuration; public issue authors cannot steer generation.
    page = 1
    while True:
        response = requests.get(f"https://api.github.com/repos/{repository}/issues",
                                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                                params={"state": "open", "creator": repository.split('/')[0],
                                        "sort": "created", "direction": "desc", "per_page": 100, "page": page}, timeout=15)
        response.raise_for_status()  # Never resume removed interests on a network failure.
        issues = response.json()
        for issue in issues:
            if issue.get("title") != TITLE or "pull_request" in issue:
                continue
            if issue.get("user", {}).get("login", "").casefold() != repository.split('/')[0].casefold():
                continue
            payload = json.loads(issue.get("body") or "{}")
            if payload.get("kind") == KIND:
                return validate_interests(payload["interests"])
        if len(issues) < 100:
            return defaults
        page += 1
