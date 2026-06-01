# Atlassian MCP server (Jira + Confluence)

Packages the [sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian)
engine as a server you run like the others (`python server.py`). One instance serves
**both Jira and Confluence**, read and write.

## Tools
~49 Jira + ~24 Confluence tools (`jira_search`, `jira_get_issue`, `jira_create_issue`,
`confluence_search`, `confluence_get_page`, `confluence_create_page`, …). The exact set
depends on which services you configure and your account's permissions.

## Install & run

```bash
cd servers/atlassian
./install.sh                       # creates .venv, installs mcp-atlassian
cp .env.example .env               # fill in JIRA_URL / tokens / CONFLUENCE_URL
./.venv/bin/python server.py       # streamable HTTP at http://127.0.0.1:9004/mcp
```

Or Docker:
```bash
docker build -t atlassian-mcp .
docker run --rm -p 9004:9004 \
  -e JIRA_URL=https://jira.yourco.com -e JIRA_PERSONAL_TOKEN=<pat> \
  -e CONFLUENCE_URL=https://confluence.yourco.com -e CONFLUENCE_PERSONAL_TOKEN=<pat> \
  atlassian-mcp
```

## Auth options (Server/DC)

Per product, pick one (auto-detected — PAT wins if set):
- **Personal Access Token**: `JIRA_PERSONAL_TOKEN` / `CONFLUENCE_PERSONAL_TOKEN`
- **Username + password (basic auth)**: `JIRA_USERNAME` + `JIRA_API_TOKEN` and/or
  `CONFLUENCE_USERNAME` + `CONFLUENCE_API_TOKEN`. On Server/DC the `*_API_TOKEN` field
  holds your **password** (it doubles as the password — there is no `*_PASSWORD` var).

## Auth model (read shared, write per-user)
- The tokens in `.env` should be a **read-only service account** → no-token requests
  (general reads) use it; Atlassian denies writes via it.
- A user's **own PAT**, forwarded by the registry when the catalog entry is
  `forward_auth: true`, takes precedence → that request acts as the user (their reads + writes).

## Publish to the registry
```bash
curl -X POST localhost:8000/catalog -H 'Content-Type: application/json' \
  -d '{"name":"Atlassian","base_url":"http://127.0.0.1:9004/mcp","transport":"http","forward_auth":true}'
```

> The machine running this must reach your Jira/Confluence URLs (VPN/network). If the
> server starts but shows **0 tools** in the catalog, it couldn't authenticate/reach
> Atlassian — check the PATs, URLs, and run with the `-v` logs.
>
> No credentials yet? Use the credential-free **mock** instead:
> `ATL_MODE=all ATL_PORT=9004 python examples/atlassian_mock.py`
