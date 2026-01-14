import socket
from datetime import datetime, timezone
from urllib.parse import unquote
from .models import Request, ResponseSpec


class Engine:
    def handle_connection(self, conn: socket.socket) -> None:
        try:
            self.process(conn)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def process(self, conn: socket.socket) -> None:
        raise NotImplementedError


class HTTPEngine(Engine):
    def __init__(self, config, request_handler, server_name=None) -> None:
        self.config = config
        self.request_handler = request_handler
        if server_name is None:
            server_name = f"python/{socket.gethostname()}"
        self.server_name = server_name


    def process(self, conn: socket.socket) -> None:
        try:
            raw = self._read_headers(conn)
            if raw is None:
                return

            req = self._parse_request(raw)
            if req.method.upper() not in ("GET", "HEAD"):
                return self._send(conn, req.method, self._simple_response(405, "Method Not Allowed"))
            resp = self.request_handler.handle(req)

            self._send(conn, req.method, resp)

        except (socket.timeout, TimeoutError):
            return
        except ValueError:
            self._send(conn, "GET", self._simple_response(400, "Bad Request"))
            return
        except Exception:
            self._send(conn, "GET", self._simple_response(500, "Internal Server Error"))
            return

    def _read_headers(self, conn: socket.socket) -> bytes | None:
        buf = bytearray()
        while True:
            if b"\r\n\r\n" in buf:
                return bytes(buf)
            if len(buf) > self.config.max_header_bytes:
                return bytes(buf)
            chunk = conn.recv(self.config.chunk_size)
            if chunk == b"":
                return None
            buf.extend(chunk)

    def _parse_request(self, raw: bytes) -> Request:
        head, _, _ = raw.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        if not lines:
            raise ValueError("empty request")

        request_line = lines[0].decode("iso-8859-1")
        parts = request_line.split()
        if len(parts) != 3:
            raise ValueError("bad request line")

        method, target, version = parts
        if not version.startswith("HTTP/"):
            raise ValueError("bad http version")

        headers = {}
        for bline in lines[1:]:
            if not bline:
                continue
            line = bline.decode("iso-8859-1", errors="ignore")
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

        path = target.split("?", 1)[0]
        path = unquote(path)

        return Request(method=method, target=target, path=path, version=version, headers=headers)

    def _send(self, conn: socket.socket, method: str, resp: ResponseSpec) -> None:
        method = method.upper()
        head_only = (method == "HEAD")

        headers = dict(resp.headers)
        headers.setdefault("Date", self._http_date())
        headers.setdefault("Server", self.server_name)
        headers.setdefault("Connection", "close")
        headers.setdefault("Content-Length", str(resp.body_size))

        status_line = f"HTTP/1.1 {resp.status} {resp.reason}\r\n"
        header_block = status_line + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
        conn.sendall(header_block.encode("iso-8859-1"))

        if head_only:
            return

        if resp.status == 200 and resp.body_path:
            self._send_file(conn, resp.body_path)

    def _send_file(self, conn: socket.socket, path: str) -> None:
        with open(path, "rb") as f:
            while True:
                data = f.read(self.config.chunk_size)
                if not data:
                    break
                conn.sendall(data)

    def _simple_response(self, status: int, reason: str) -> ResponseSpec:
        return ResponseSpec(status=status, reason=reason, headers={"Content-Type": "text/plain; charset=utf-8"}, body_size=0)

    @staticmethod
    def _http_date() -> str:
        dt = datetime.now(timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
