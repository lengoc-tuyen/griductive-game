"""Entry point: launch the Griductive Web Server & GUI (frontend.gui.app)."""

from __future__ import annotations

import argparse
from pathlib import Path

from frontend.gui.app import run_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Launch the Griductive Solver Web Application.")
    parser.add_argument(
        "puzzle",
        nargs="?",
        default=None,
        help="Optional path to a puzzle JSON file to load on startup.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port number (default: 5000)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the web browser on startup.",
    )
    args = parser.parse_args(argv)
    puzzle_path = Path(args.puzzle) if args.puzzle else None
    run_server(
        host=args.host,
        port=args.port,
        puzzle_path=puzzle_path,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
