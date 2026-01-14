import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    root: str = "."
    workers: int = 4
    queue_size: int = 1000
    backlog: int = 128
    recv_timeout: float = 2.0
    accept_timeout: float = 1.0
    max_header_bytes: int = 65536
    chunk_size: int = 64 * 1024
    debug: bool = True
