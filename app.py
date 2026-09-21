#!/usr/bin/env python3
"""
Resume-Tailor Web Application Entrypoint.
Usage:
    python app.py
    python app.py --port 8080 --no-open
"""

import argparse
import sys
from pathlib import Path

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

load_dotenv()

from src.web_app import start_server


def main():
    parser = argparse.ArgumentParser(description="Resume-Tailor Web Application")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    parser.add_argument("--no-open", action="store_true", help="Do not automatically open the browser")

    args = parser.parse_args()
    start_server(host=args.host, port=args.port, auto_open=not args.no_open)


if __name__ == "__main__":
    main()
