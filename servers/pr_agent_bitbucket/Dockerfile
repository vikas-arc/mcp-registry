FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# pr-agent hard-pins old uvicorn/starlette that conflict with mcp's pins. We only
# use pr-agent's library API (not its web server), so install pr-agent first, then
# let mcp bump uvicorn/starlette. The resulting pip "conflict" warning is benign.
RUN pip install --no-cache-dir pr-agent==0.35.0 \
 && pip install --no-cache-dir "mcp>=1.5"

COPY server.py .

# Provide at runtime:
#   BITBUCKET_SERVER_URL, BITBUCKET_SERVER_TOKEN, OPENAI_KEY, (PR_AGENT_MODEL)
EXPOSE 9003
CMD ["python", "server.py"]
