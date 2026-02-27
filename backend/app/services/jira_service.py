import base64
import logging

import httpx

logger = logging.getLogger(__name__)


def _adf_to_text(node: dict | list | None) -> str:
    """Recursively extract plain text from an Atlassian Document Format (ADF) node."""
    if not node:
        return ""
    if isinstance(node, list):
        return "\n".join(_adf_to_text(n) for n in node if n)
    if isinstance(node, str):
        return node
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_adf_to_text(c) for c in node.get("content", [])]
    sep = "\n" if node.get("type") in (
        "paragraph", "heading", "listItem", "bulletList", "orderedList", "blockquote"
    ) else ""
    return sep.join(p for p in parts if p)


def _auth_headers(email: str, api_token: str) -> dict:
    cred = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    return {
        "Authorization": f"Basic {cred}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def fetch_project_tickets(
    workspace_url: str,
    email: str,
    api_token: str,
    project_key: str,
    max_results: int = 20,
) -> list[dict]:
    """Fetch open tickets from a Jira project ordered by most recently updated."""
    base = workspace_url.rstrip("/")
    headers = _auth_headers(email, api_token)
    jql = f'project = "{project_key}" AND statusCategory != Done ORDER BY updated DESC'

    async with httpx.AsyncClient(timeout=15) as client:
        # POST /rest/api/3/search/jql — replaces deprecated GET /rest/api/3/search
        resp = await client.post(
            f"{base}/rest/api/3/search/jql",
            headers=headers,
            json={"jql": jql, "maxResults": max_results, "fields": ["summary", "status", "assignee", "priority"]},
        )
        if resp.status_code != 200:
            logger.warning(f"[Jira] Failed to fetch tickets for {project_key}: {resp.status_code}")
            return []

        tickets = []
        for issue in resp.json().get("issues", []):
            fields = issue.get("fields", {})
            assignee = fields.get("assignee")
            priority = fields.get("priority")
            tickets.append({
                "id": issue["key"],
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", ""),
                "status_category": fields.get("status", {}).get("statusCategory", {}).get("colorName", ""),
                "assignee": assignee["displayName"] if assignee else None,
                "priority": priority["name"] if priority else None,
                "url": f"{base}/browse/{issue['key']}",
            })
        return tickets


async def fetch_ticket_detail(
    workspace_url: str,
    email: str,
    api_token: str,
    ticket_id: str,
) -> dict | None:
    """
    Fetch a single Jira ticket's summary + full description (ADF → plain text).
    Returns None if the request fails.
    """
    base = workspace_url.rstrip("/")
    headers = _auth_headers(email, api_token)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/rest/api/3/issue/{ticket_id}",
            headers=headers,
            params={"fields": "summary,description,issuetype,priority,assignee,status"},
        )
        if resp.status_code != 200:
            logger.warning(f"[Jira] Failed to fetch ticket {ticket_id}: {resp.status_code}")
            return None

        data = resp.json()
        fields = data.get("fields", {})
        description_text = _adf_to_text(fields.get("description"))
        return {
            "id": ticket_id,
            "summary": fields.get("summary", ""),
            "description": description_text,
            "issue_type": (fields.get("issuetype") or {}).get("name", ""),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "assignee": ((fields.get("assignee") or {}).get("displayName")),
            "status": (fields.get("status") or {}).get("name", ""),
            "url": f"{base}/browse/{ticket_id}",
        }


async def update_ticket_status(
    workspace_url: str,
    email: str,
    api_token: str,
    ticket_id: str,
    status: str,
    pr_url: str | None = None,
) -> bool:
    """
    Transition a Jira ticket to the given status name and optionally
    attach a remote link to the PR.
    """
    base = workspace_url.rstrip("/")
    headers = _auth_headers(email, api_token)

    async with httpx.AsyncClient(timeout=15) as client:
        # Get available transitions for this ticket
        resp = await client.get(
            f"{base}/rest/api/3/issue/{ticket_id}/transitions",
            headers=headers,
        )
        if resp.status_code != 200:
            logger.warning(f"[Jira] Failed to fetch transitions for {ticket_id}: {resp.status_code} {resp.text}")
            return False

        transitions = resp.json().get("transitions", [])

        # Exact match first, then partial
        target = next((t for t in transitions if t["name"].lower() == status.lower()), None)
        if not target:
            target = next((t for t in transitions if status.lower() in t["name"].lower()), None)

        if target:
            resp = await client.post(
                f"{base}/rest/api/3/issue/{ticket_id}/transitions",
                headers=headers,
                json={"transition": {"id": target["id"]}},
            )
            if resp.status_code not in (200, 204):
                logger.warning(f"[Jira] Transition to '{status}' failed for {ticket_id}: {resp.status_code}")
        else:
            logger.warning(f"[Jira] No transition named '{status}' found for {ticket_id}. Available: {[t['name'] for t in transitions]}")

        # Attach PR link as a remote link
        if pr_url:
            resp = await client.post(
                f"{base}/rest/api/3/issue/{ticket_id}/remotelink",
                headers=headers,
                json={
                    "globalId": f"pr-{pr_url}",
                    "object": {
                        "url": pr_url,
                        "title": "Pull Request",
                        "icon": {
                            "url16x16": "https://github.githubassets.com/favicons/favicon.svg",
                            "title": "GitHub",
                        },
                        "status": {"resolved": False},
                    },
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(f"[Jira] Remote link failed for {ticket_id}: {resp.status_code}")
            else:
                logger.info(f"[Jira] PR linked to {ticket_id}: {pr_url}")

    return True
