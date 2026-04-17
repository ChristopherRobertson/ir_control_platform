"""Run the workflow-first simulator shell locally."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from wsgiref.simple_server import make_server


ROOT = Path(__file__).resolve().parent

for relative_path in (
    "contracts/src",
    "platform/src",
    "drivers/src",
    "experiment-engine/src",
    "data-pipeline/src",
    "processing/src",
    "analysis/src",
    "ui-shell/src",
    "reports/src",
    "simulators/src",
):
    package_root = ROOT / relative_path
    if package_root.exists():
        sys.path.insert(0, str(package_root))

from ircp_platform import create_simulator_app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the IR control platform workflow shell.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address for the local WSGI server.")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local WSGI server.")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Optional storage root for saved sessions. Defaults to .local_state under the repo.",
    )
    args = parser.parse_args()

    app = create_simulator_app(storage_root=args.storage_root)
    with make_server(args.host, args.port, app) as server:
        print(f"Serving IR control platform UI at http://{args.host}:{args.port}")
        if args.storage_root is not None:
            print(f"Using storage root: {args.storage_root.resolve()}")
        server.serve_forever()


if __name__ == "__main__":
    main()
