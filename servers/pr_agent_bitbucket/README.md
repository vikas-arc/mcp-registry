# PR-Agent MCP server — Bitbucket Server

A custom MCP server that wraps [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent)
and exposes its PR commands as tools, hard-wired to the **Bitbucket Server /
Data Center** git provider.

## Tools

| Tool | What it does |
| --- | --- |
| `review_pr(pr_url)` | AI code review, posted as a PR comment |
| `describe_pr(pr_url)` | Generates a PR title + description |
| `improve_pr(pr_url)` | Posts concrete code-improvement suggestions |
| `ask_pr(pr_url, question)` | Answers a free-form question about the PR |

`pr_url` is a full Bitbucket Server URL, e.g.
`https://bitbucket.yourco.com/projects/KEY/repos/my-repo/pull-requests/123`.

## Install (Python 3.13 or 3.12)

pr-agent **does** install on Python 3.13. The only wrinkle: pr-agent hard-pins old
`uvicorn`/`starlette`, which clash with `mcp`'s newer pins. That clash is just a
*declaration* — we call pr-agent's library API (`PRAgent.handle_request`), not its
bundled web server — so installing pr-agent first and then `mcp` (which bumps
uvicorn/starlette) is safe at runtime.

**⚠️ `pip install -r requirements.txt` FAILS** (single-resolution can't satisfy
uvicorn==0.22.0 *and* mcp). Install **sequentially** — run `./install.sh`, or:

```bash
cd servers/pr_agent_bitbucket
python3.13 -m venv .venv && source .venv/bin/activate
pip install pr-agent==0.35.0
pip install "mcp>=1.5"          # bumps uvicorn/starlette — benign pip warning

export BITBUCKET_SERVER_URL=https://bitbucket.yourco.com
export BITBUCKET_SERVER_TOKEN=<bitbucket http access token>   # used as bearer_token
export OPENAI_KEY=<your openai key>
export PR_AGENT_MODEL=gpt-4o        # optional
python server.py     # streamable HTTP at http://127.0.0.1:9003/mcp
```

Or just use the **Dockerfile** (does the two-step install for you):

```bash
docker build -t pragent-bbs .
docker run --rm -p 9003:9003 \
  -e BITBUCKET_SERVER_URL=https://bitbucket.yourco.com \
  -e BITBUCKET_SERVER_TOKEN=<token> -e OPENAI_KEY=<key> pragent-bbs
```

> The server imports pr-agent lazily, so it can start and list tools (and be
> published to the catalog) even from the main registry venv that has only `mcp`.
> Executing a review needs pr-agent installed (above) + the env vars + credentials.

It maps to pr-agent settings:
`config.git_provider=bitbucket_server`, `bitbucket_server.url`,
`bitbucket_server.bearer_token` (or `.username` + `.password`), `openai.key`.

### Auth (pick one)
- **HTTP access token** — `BITBUCKET_SERVER_TOKEN`. Recommended, and **required for
  git-clone operations** pr-agent performs for some commands.
- **Username + password (basic auth)** — `BITBUCKET_SERVER_USERNAME` +
  `BITBUCKET_SERVER_PASSWORD` (used when no token is set). Works for the API-based
  commands; commands that need a local clone still require a token.

> The server **starts and lists its tools without** pr-agent installed or
> credentials set (pr-agent is imported lazily). That's enough to publish it to
> the registry catalog; actual tool *execution* needs the deps + env above.

## Publish to the registry

```bash
curl -X POST http://localhost:8000/catalog -H 'Content-Type: application/json' \
  -d '{"name":"PR Agent (Bitbucket Server)","base_url":"http://127.0.0.1:9003/mcp","transport":"http","description":"AI PR review/describe/improve/ask for Bitbucket Server"}'
```

Teammates then connect it from the registry UI like any other server. Tools appear
namespaced, e.g. `pr_agent_bitbucket_server__review_pr`.
