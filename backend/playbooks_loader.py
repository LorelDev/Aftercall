"""Load crisis playbooks (YAML). The engine is crisis-agnostic: everything
crisis-specific lives here, a new crisis is a new YAML file, not new code."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

PLAYBOOKS_DIR = os.environ.get(
    "PLAYBOOKS_DIR", os.path.join(os.path.dirname(__file__), "..", "playbooks")
)


class PlaybookError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def load_playbook(playbook_id: str) -> dict[str, Any]:
    safe = os.path.basename(playbook_id)  # no path traversal
    path = os.path.join(PLAYBOOKS_DIR, f"{safe}.yaml")
    if not os.path.exists(path):
        raise PlaybookError(f"unknown playbook: {playbook_id}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def list_playbooks() -> list[str]:
    if not os.path.isdir(PLAYBOOKS_DIR):
        return []
    return sorted(
        f[:-5] for f in os.listdir(PLAYBOOKS_DIR) if f.endswith(".yaml")
    )
