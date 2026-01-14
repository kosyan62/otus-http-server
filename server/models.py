from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class Request:
    method: str
    target: str
    path: str
    version: str
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResponseSpec:
    status: int
    reason: str
    headers: Dict[str, str] = field(default_factory=dict)
    body_path: Optional[str] = None
    body_size: int = 0
