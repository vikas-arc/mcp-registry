"""PR-Agent MCP server — Bitbucket Server only.

Wraps qodo-ai/pr-agent (https://github.com/qodo-ai/pr-agent) and exposes its PR
commands as MCP tools, hard-wired to the Bitbucket **Server / Data Center**
provider (not Bitbucket Cloud).

Environment (needed to *run* tools; NOT needed just to list/publish them):
  BITBUCKET_SERVER_URL     e.g. https://bitbucket.yourco.com
  BITBUCKET_SERVER_TOKEN   a Bitbucket Server HTTP access token (used as bearer)
  OPENAI_KEY               your OpenAI API key
  PR_AGENT_MODEL           optional model, default "gpt-4o"

Run:
  pip install -r requirements.txt
  python server.py          # streamable HTTP at http://127.0.0.1:9003/mcp

pr-agent posts its output (review / description / suggestions) as comments on the
target pull request, so each tool returns a short status string.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PR Agent (Bitbucket Server)", host="127.0.0.1", port=9003)


def _load_dotenv() -> None:
    """Load a local .env (so `cp .env.example .env && python server.py` works)."""
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()
_configured = False


def _configure() -> None:
    """Point pr-agent at Bitbucket Server. Imported lazily so the MCP server can
    start and list its tools without pr-agent installed or credentials present."""
    global _configured
    if _configured:
        return
    from pr_agent.config_loader import get_settings

    url = os.environ.get("BITBUCKET_SERVER_URL")
    key = os.environ.get("OPENAI_KEY")
    # Auth: a bearer token, OR username + password (basic auth). pr-agent uses the
    # token if set, else falls back to username/password.
    token = os.environ.get("BITBUCKET_SERVER_TOKEN")
    username = os.environ.get("BITBUCKET_SERVER_USERNAME")
    password = os.environ.get("BITBUCKET_SERVER_PASSWORD")

    missing = []
    if not url:
        missing.append("BITBUCKET_SERVER_URL")
    if not key:
        missing.append("OPENAI_KEY")
    if not token and not (username and password):
        missing.append("BITBUCKET_SERVER_TOKEN (or BITBUCKET_SERVER_USERNAME + BITBUCKET_SERVER_PASSWORD)")
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))

    s = get_settings()
    s.set("config.git_provider", "bitbucket_server")
    s.set("config.model", os.environ.get("PR_AGENT_MODEL", "gpt-4o"))
    s.set("bitbucket_server.url", url)
    if token:
        s.set("bitbucket_server.bearer_token", token)
    else:
        s.set("bitbucket_server.username", username)
        s.set("bitbucket_server.password", password)
    s.set("openai.key", key)
    _configured = True


async def _run(pr_url: str, command: list[str]) -> str:
    from pr_agent.agent.pr_agent import PRAgent

    _configure()
    try:
        ok = await PRAgent().handle_request(pr_url, command)
    except Exception as exc:  # noqa: BLE001 — return the failure to the caller
        return f"❌ pr-agent `{command[0]}` failed for {pr_url}: {exc}"
    if ok:
        return f"✅ pr-agent `{command[0]}` ran on {pr_url}; results posted to the Bitbucket PR."
    return f"⚠️ pr-agent `{command[0]}` did not complete for {pr_url}. Check server logs / credentials."


@mcp.tool()
async def review_pr(pr_url: str) -> str:
    """Run an AI code review on a Bitbucket Server pull request and post it as a comment.

    pr_url: full Bitbucket Server PR URL, e.g.
      https://bitbucket.yourco.com/projects/KEY/repos/my-repo/pull-requests/123
    """
    return await _run(pr_url, ["review"])


@mcp.tool()
async def describe_pr(pr_url: str) -> str:
    """Generate a title and structured description for a Bitbucket Server PR and post it."""
    return await _run(pr_url, ["describe"])


@mcp.tool()
async def improve_pr(pr_url: str) -> str:
    """Generate concrete code-improvement suggestions for a Bitbucket Server PR."""
    return await _run(pr_url, ["improve"])


@mcp.tool()
async def ask_pr(pr_url: str, question: str) -> str:
    """Ask a free-form question about a Bitbucket Server PR (e.g. 'is this safe to merge?')."""
    return await _run(pr_url, ["ask", question])


@mcp.tool()
async def update_changelog_pr(pr_url: str) -> str:
    """Update the CHANGELOG based on a Bitbucket Server PR's changes."""
    return await _run(pr_url, ["update_changelog"])


@mcp.tool()
async def add_docs_pr(pr_url: str) -> str:
    """Generate docstrings/documentation suggestions for new code in a Bitbucket Server PR."""
    return await _run(pr_url, ["add_docs"])


# Not exposed — unsupported by the Bitbucket Server provider:
#   generate_labels / similar_issue  (no labels / issue-comments support)
#   ask_line                         (no inline file comments support)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
