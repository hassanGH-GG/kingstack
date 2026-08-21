from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    home: Path
    repo: Path
    runtime: Path
    claude_home: Path
    codex_home: Path

    @classmethod
    def for_home(cls, home: Path) -> "Paths":
        home = home.expanduser().resolve()
        return cls(home, home / "Desktop/Work/kingstack", home / ".kingstack",
                   home / ".claude", home / ".codex")
