from __future__ import annotations

import argparse
import json
import mimetypes
import webbrowser
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .domain import Evidence, Horizon
from .engine import MacroEngine


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


def load_evidence(path: Path) -> list[Evidence]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Evidence(
            **{
                **item,
                "horizon": Horizon(item["horizon"]),
                "observed_at": datetime.fromisoformat(item["observed_at"]),
            }
        )
        for item in raw
    ]


class DashboardHandler(BaseHTTPRequestHandler):
    engine = MacroEngine()
    asset_id = "XAUUSD"
    evidence_path = Path("examples/xauusd_evidence.json")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/assessment":
            self._assessment()
            return
        if path == "/api/health":
            self._json({"status": "ok"})
            return
        if path == "/":
            path = "/index.html"
        target = (STATIC / path.lstrip("/")).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _assessment(self) -> None:
        try:
            evidence = load_evidence(self.evidence_path)
            assessment = self.engine.assess(self.asset_id, evidence)
            pack = self.engine.registry.load(self.asset_id)
            self._json(
                {
                    "assessment": asdict(assessment),
                    "asset": {
                        "id": pack.asset_id,
                        "name": pack.display_name,
                        "metadata": pack.metadata,
                    },
                    "data_status": {
                        "mode": "sample",
                        "message": "Bundled demonstration evidence; live connectors are not configured",
                        "newest_observation": max(
                            (item.observed_at for item in evidence), default=None
                        ),
                    },
                    "factors": [asdict(factor) for factor in pack.factors],
                    "evidence": [asdict(item) for item in evidence],
                }
            )
        except Exception as exc:  # browser receives a useful local error
            self._json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local macro dashboard")
    parser.add_argument("--asset", default="XAUUSD")
    parser.add_argument("--evidence", type=Path, default=Path("examples/xauusd_evidence.json"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()

    DashboardHandler.asset_id = args.asset.upper()
    DashboardHandler.evidence_path = args.evidence.resolve()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Macro dashboard running at {url}")
    print("Press Ctrl+C to stop.")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
