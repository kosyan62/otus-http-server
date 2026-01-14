import mimetypes
import os

from .models import Request, ResponseSpec


class FileHandler:
    def __init__(self, document_root: str) -> None:
        self.root_real = os.path.realpath(document_root)

    def handle(self, req: Request) -> ResponseSpec:
        try:
            abs_path = self._resolve(req.path)
        except PermissionError:
            return ResponseSpec(403, "Forbidden", headers={"Content-Type": "text/plain; charset=utf-8"}, body_size=0)

        if abs_path is None:
            return ResponseSpec(404, "Not Found", headers={"Content-Type": "text/plain; charset=utf-8"}, body_size=0)

        try:
            st = os.stat(abs_path)
        except OSError:
            return ResponseSpec(404, "Not Found", headers={"Content-Type": "text/plain; charset=utf-8"}, body_size=0)

        ctype, _ = mimetypes.guess_type(abs_path)
        return ResponseSpec(
            200,
            "OK",
            headers={"Content-Type": ctype or "application/octet-stream"},
            body_path=abs_path,
            body_size=st.st_size,
        )

    def _resolve(self, url_path: str) -> str | None:
        if url_path in ("", "/"):
            url_path = "/index.html"

        abs_path = self._safe_join(self.root_real, url_path)

        if os.path.isdir(abs_path):
            abs_path = os.path.join(abs_path, "index.html")

        if not os.path.exists(abs_path):
            return None

        if not os.path.isfile(abs_path) or not os.access(abs_path, os.R_OK):
            raise PermissionError("not readable")

        return abs_path

    def _safe_join(self, root_real: str, url_path: str) -> str:
        rel = url_path.lstrip("/")
        norm = os.path.normpath(rel)
        candidate = os.path.join(root_real, norm)
        real = os.path.realpath(candidate)

        root_prefix = root_real + os.sep
        if real != root_real and not real.startswith(root_prefix):
            raise PermissionError("escape root")
        return real
