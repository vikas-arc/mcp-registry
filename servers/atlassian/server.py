"""Atlassian MCP server (Jira + Confluence Server/DC).

Thin launcher so this runs like the other servers (`python server.py`). The engine
is the third-party `mcp-atlassian` package (installed via ./install.sh); this just
loads the local .env and starts it in streamable-HTTP mode.

Config (from environment or a local .env — see .env.example):
  JIRA_URL, JIRA_PERSONAL_TOKEN
  CONFLUENCE_URL, CONFLUENCE_PERSONAL_TOKEN
  ATL_PORT (default 9004), ATL_PATH (default /mcp)
  JIRA_SSL_VERIFY / CONFLUENCE_SSL_VERIFY = false   (only for self-signed certs)

Use a READ-ONLY service account for the tokens here; a user's own PAT, forwarded by
the registry when the catalog entry has forward_auth=true, takes precedence and enables
writes as that user.
"""
import os
import sys


def _load_dotenv() -> None:
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def main() -> None:
    _load_dotenv()
    port = os.environ.get("ATL_PORT", "9004")
    path = os.environ.get("ATL_PATH", "/mcp")

    # Resolve the mcp-atlassian console script next to this interpreter (venv), else PATH.
    exe = os.path.join(os.path.dirname(sys.executable), "mcp-atlassian")
    if not os.path.exists(exe):
        exe = "mcp-atlassian"

    args = [exe, "--transport", "streamable-http", "--port", port, "--path", path, "-v"]
    args += sys.argv[1:]  # pass through any extra flags
    os.execvp(exe, args)


if __name__ == "__main__":
    main()
