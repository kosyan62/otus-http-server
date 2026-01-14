import datetime
import socket
import threading
from typing import Optional, Tuple


from .config import Config
from .pool import WorkerPool
from .engine import Engine, HTTPEngine
from .handler import FileHandler


class ThreadedHTTPServer:
    def __init__(self, config: Config) -> None:
        self.config = config

        # Created on run()
        self._listen_sock: Optional[socket.socket] = None
        self._engine: Optional[Engine] = None
        self._pool: Optional[WorkerPool] = None

        # Stop coordination
        self._stop_event = threading.Event()

    def run(self) -> None:
        self._stop_event.clear()

        self._listen_sock = self._create_listen_socket()
        self._engine = HTTPEngine(self.config, FileHandler(self.config.root))
        self._pool = WorkerPool(self.config, self._engine)

        # Run worker pool in the background
        self._pool.start()

        # Run the accept-loop in the current thread (blocking) until stopped
        try:
            self._accept_loop()
        finally:
            self._cleanup()


    def stop(self) -> None:
        self._stop_event.set()

        # unblock accept() imediately
        if self._listen_sock is not None:
            try:
                self._listen_sock.close()
            except OSError:
                pass

    def _cleanup(self) -> None:
        # Closing listen socket unblocks accept()
        if self._listen_sock is not None:
            try:
                self._listen_sock.close()
            except OSError:
                pass

        if self._pool is not None:
            self._pool.stop()

        self._listen_sock = None
        self._pool = None
        self._engine = None

    def _create_listen_socket(self) -> socket.socket:
        """
        Create/bind/listen.
        Uses SO_REUSEADDR to make restarts easier during development.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        sock.bind((self.config.host, self.config.port))
        sock.listen(self.config.backlog)

        sock.settimeout(self.config.accept_timeout)

        return sock

    def _accept_loop(self) -> None:
        """
        Accept connections and submit to worker pool.
        Exits when stop_event is set or listen socket is closed.
        """
        assert self._listen_sock is not None
        assert self._pool is not None

        while not self._stop_event.is_set():
            try:
                conn, addr = self._listen_sock.accept()
            except socket.timeout:
                if self.config.debug:
                    print(f"Accept loop iteration...")
                continue
            except OSError:
                # socket was likely closed during stop()
                break

            # Configure client connection socket here (timeouts, etc.)
            try:
                conn.settimeout(self.config.recv_timeout)
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                try:
                    conn.close()
                except OSError:
                    pass
                continue

            # Submit to pool. Pool must close conn after handling.
            try:
                self._pool.submit(conn, addr)
            except Exception:
                try:
                    conn.close()
                except OSError:
                    pass
