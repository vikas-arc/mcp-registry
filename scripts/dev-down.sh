#!/usr/bin/env bash
# Stop all local dev processes started by dev-up.sh (and any MCP servers on the dev ports).
for p in 8000 8800 9001 9002 9003 9004 9005; do
  pid="$(lsof -nP -iTCP:"$p" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -n "$pid" ]; then kill $pid 2>/dev/null && echo "stopped :$p (pid $pid)"; fi
done
echo "done."
