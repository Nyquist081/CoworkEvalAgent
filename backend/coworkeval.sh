#!/bin/bash
# CoworkEval CLI wrapper
cd "$(dirname "$0")"
uv run python -m src.cli "$@"
