#!/usr/bin/env bash
# Local dev launcher — brings up the registry + an Atlassian MOCK server on this machine.
# No credentials needed (mock advertises the tool names). Stop with scripts/dev-down.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LOGS="$ROOT/.devlogs"; mkdir -p "$LOGS"

# 1. venv + deps
if [ ! -d .venv ]; then
  echo "Creating .venv (Python 3.13)…"
  python3.13 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi
PY="./.venv/bin/python"

# 2. .env
[ -f .env ] || cp .env.example .env

# 3. MongoDB reachable?
if ! "$PY" -c "import socket; socket.create_connection(('localhost',27017),2)" 2>/dev/null; then
  echo "❌ MongoDB not reachable on localhost:27017."
  echo "   Start it first, e.g.:"
  echo "     brew services start mongodb-community@7.0"
  echo "     # or: docker run -d --name mongo -p 27017:27017 mongo:7"
  exit 1
fi

start() {  # name port cmd...
  local name="$1" port="$2"; shift 2
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  • $name already running on :$port"; return
  fi
  nohup "$@" > "$LOGS/$name.log" 2>&1 &
  echo "  • started $name on :$port  (log: .devlogs/$name.log)"
}

echo "Starting services…"
start registry 8000 "$PY" -m uvicorn app.main:app --port 8000
start atlassian-mock 9004 env ATL_MODE=all ATL_PORT=9004 "$PY" examples/atlassian_mock.py

# 4. wait for the registry health endpoint
for _ in $(seq 1 30); do curl -sf localhost:8000/health >/dev/null 2>&1 && break; sleep 0.5; done

# 5. publish the mock to the catalog (once)
if ! curl -s localhost:8000/catalog -H 'X-User-Id: admin' | grep -q '"name":"Atlassian"'; then
  curl -s -X POST localhost:8000/catalog -H 'Content-Type: application/json' \
    -d '{"name":"Atlassian","base_url":"http://127.0.0.1:9004/mcp","transport":"http","forward_auth":true}' >/dev/null \
    && echo "  • published Atlassian (mock) to the catalog"
fi

cat <<EOF

✅ Up. Open:
   Registry UI : http://localhost:8000/ui/
   API docs    : http://localhost:8000/docs

Next:
   • swap the mock for the real Atlassian server — see SETUP.md / README
   • start the agent service: cd agent && uvicorn web:app --port 8800
   • stop everything: ./scripts/dev-down.sh
EOF
