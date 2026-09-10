from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class BenchmarkCase:
    instance_id: str
    task_type: str

    repo: str
    base_commit: str

    problem_statement: str

    evaluator: str

    language: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None