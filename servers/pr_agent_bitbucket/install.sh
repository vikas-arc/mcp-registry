#!/usr/bin/env bash
# Two-step install — REQUIRED.
# pr-agent pins uvicorn==0.22.0 while mcp needs a newer uvicorn, so a single
# `pip install pr-agent mcp` (or `pip install -r requirements.txt`) fails the
# resolver. Installing sequentially works: pr-agent first, then mcp bumps
# uvicorn/starlette. That's safe — we use pr-agent's library API, not its web server.
set -euo pipefail

pip install pr-agent==0.35.0
pip install "mcp>=1.5"

echo "✅ Installed. (The uvicorn/starlette 'conflict' warning above is expected and benign.)"
