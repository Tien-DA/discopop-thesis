from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class BenchmarkCase:
    index: int
    repository: str
    name: str
    workspace: Path
    task: str
    build_command: str
    test_command: str
    profiling_command: str | None
    validator: Optional[str] = None