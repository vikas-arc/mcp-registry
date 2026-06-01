#!/usr/bin/env bash
# Install the Atlassian MCP server into a local venv.
set -euo pipefail
cd "$(dirname "$0")"

python3.13 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

echo "✅ Installed."
echo "   1. cp .env.example .env  &&  fill in JIRA_URL / tokens / CONFLUENCE_URL"
echo "   2. ./.venv/bin/python server.py        # http://127.0.0.1:9004/mcp"
