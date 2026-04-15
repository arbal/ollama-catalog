import json
from pathlib import Path
from typing import Set

STATE_FILE = Path("out/seen_slugs.json")

class StateManager:
    def __init__(self, state_file: Path = STATE_FILE, incremental_stop: int = 3):
        self.state_file = state_file
        self.incremental_stop = incremental_stop
        self.seen_slugs: Set[str] = set()
        self.load()

    def load(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    slugs = json.load(f)
                    self.seen_slugs = set(slugs)
            except (json.JSONDecodeError, IOError):
                self.seen_slugs = set()
        else:
            self.seen_slugs = set()

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(sorted(list(self.seen_slugs)), f, indent=2)

    def is_seen(self, slug: str) -> bool:
        return slug in self.seen_slugs

    def mark_seen(self, slug: str):
        self.seen_slugs.add(slug)

    def merge(self, new_slugs: Set[str]):
        self.seen_slugs.update(new_slugs)
