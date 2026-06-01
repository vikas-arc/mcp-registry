"""MOCK Atlassian MCP server — tool NAMES only, no real logic.

Advertises the same tool names as sooperset/mcp-atlassian so they show in the
registry/agent UI WITHOUT real credentials. Calls just return a mock string.

ATL_MODE selects which tools to expose:
  read  (default) -> read-only tools (get_/search/download/…)
  write           -> mutating tools (create/update/delete/add/…)
  all             -> everything
ATL_PORT sets the port (default 9004).
"""
import os
from mcp.server.fastmcp import FastMCP

JIRA = ['add_comment', 'add_issues_to_sprint', 'add_watcher', 'add_worklog', 'batch_create_issues', 'batch_create_versions', 'batch_get_changelogs', 'create_issue', 'create_issue_link', 'create_remote_issue_link', 'create_sprint', 'create_version', 'delete_issue', 'download_attachments', 'edit_comment', 'get_agile_boards', 'get_all_projects', 'get_board_issues', 'get_field_options', 'get_issue', 'get_issue_dates', 'get_issue_development_info', 'get_issue_images', 'get_issue_proforma_forms', 'get_issue_sla', 'get_issue_watchers', 'get_issues_development_info', 'get_link_types', 'get_proforma_form_details', 'get_project_components', 'get_project_issues', 'get_project_versions', 'get_queue_issues', 'get_service_desk_for_project', 'get_service_desk_queues', 'get_sprint_issues', 'get_sprints_from_board', 'get_transitions', 'get_user_profile', 'get_worklog', 'link_to_epic', 'remove_issue_link', 'remove_watcher', 'search', 'search_fields', 'transition_issue', 'update_issue', 'update_proforma_form_answers', 'update_sprint']
CONFLUENCE = ['add_comment', 'add_label', 'create_page', 'delete_attachment', 'delete_page', 'download_attachment', 'download_content_attachments', 'get_attachments', 'get_comments', 'get_labels', 'get_page', 'get_page_children', 'get_page_diff', 'get_page_history', 'get_page_images', 'get_page_views', 'move_page', 'reply_to_comment', 'search', 'search_user', 'update_page', 'upload_attachment', 'upload_attachments']

# A tool is a WRITE tool if (after the jira_/confluence_ prefix) it starts with one
# of these verbs; everything else is READ.
WRITE_PREFIXES = ("create", "update", "delete", "add", "remove", "upload",
                  "move", "transition", "reply", "edit", "link", "batch_create")

def is_write(short: str) -> bool:
    return any(short.startswith(w) for w in WRITE_PREFIXES)

MODE = os.environ.get("ATL_MODE", "read").lower()
PORT = int(os.environ.get("ATL_PORT", "9004"))
NAME = {"read": "Atlassian (read)", "write": "Atlassian (write)"}.get(MODE, "Atlassian")

mcp = FastMCP(NAME, host="127.0.0.1", port=PORT)

def _make(tool_name: str):
    async def _tool(query: str = "", id: str = "") -> str:
        return f"[mock] {tool_name} — swap in the real mcp-atlassian to enable."
    _tool.__name__ = tool_name
    return _tool

def _want(short: str) -> bool:
    if MODE == "all":
        return True
    return is_write(short) if MODE == "write" else not is_write(short)

for _svc, _names in (("jira", JIRA), ("confluence", CONFLUENCE)):
    for _n in _names:
        if _want(_n):
            full = f"{_svc}_{_n}"
            mcp.tool(name=full, description=f"[mock] {_svc}: {_n}")(_make(full))

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
