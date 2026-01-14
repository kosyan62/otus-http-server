# server/pool.py
from __future__ import annotations

import queue
import socket
import threading
from dataclasses import dataclass
from typing import Tuple, Optional

from .config import Config
from .engine import Engine


@dataclass(frozen=True)
class Task:
    conn: socket.socket
    addr: Tuple[str, int]


class WorkerPool:
    def __init__(self, config: Config, engine: Engine) -> None:
        self.config = config
        self.engine = engine

        maxsize = getattr(config, "queue_size", 0) or 0
        self._queue: queue.Queue[Task] = queue.Queue(maxsize=maxsize)

        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._started = False
        self._lock = threading.Lock()

        self._poll_timeout = 0.2

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_event.clear()

            for i in range(self.config.workers):
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"worker-{i}",
                    daemon=True,
                )
                self._threads.append(t)
                t.start()

    def submit(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        if self._stop_event.is_set():
            try:
                conn.close()
            except OSError:
                pass
            return

        task = Task(conn=conn, addr=addr)
        try:
            if self.config.debug:
                print(f"Queueing connection from {addr}")
            self._queue.put(task, block=False)
        except queue.Full:
            if self.config.debug:
                print("Worker queue full; dropping connection")
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stop_event.set()

        for t in self._threads:
            t.join(timeout=5)

        with self._lock:
            self._threads.clear()
            self._started = False

    def _worker_loop(self) -> None:
        while True:
            if self._stop_event.is_set():
                return

            try:
                task = self._queue.get(timeout=self._poll_timeout)
            except queue.Empty:
                continue

            try:
                self._handle_connection(task.conn)
            finally:
                try:
                    self._queue.task_done()
                except ValueError:
                    pass

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            if self.config.debug:
                print(f"Handling connection from {conn.getpeername()}")
            return self.engine.handle_connection(conn)
        except (socket.timeout, TimeoutError):
            return
        except Exception as e:
            if self.config.debug:
                print(f"Unhandled exception in worker thread: {e}")
            return
