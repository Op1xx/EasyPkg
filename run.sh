#!/usr/bin/env bash
cd "$(dirname "$0")"
exec steam-run .venv/bin/python main.py "$@"
