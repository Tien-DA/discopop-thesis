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
    language: str = ""
    validator: Optional[str] = None
    performance_command: Optional[str] = None
    profiling_timeout_seconds: Optional[int] = None
