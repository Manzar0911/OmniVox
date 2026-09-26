"""Dynamic per-user Notion tool integration with active validation.

Allows users to provide their Notion Internal Integration Token (e.g. `ntn_...` or `secret_...`)
and seamlessly query, read, and create pages in their own Notion workspace.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import requests

from langchain_core.tools import tool

logger = logging.getLogger("omnivox.notion")
NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


def get_notion_headers(token: str) -> Dict[str, str]:
    token = token.strip()
    if token.startswith("{"):
        try:
            data = json.loads(token)
            token = data.get("access_token") or data.get("token") or token
        except Exception:
            pass
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def validate_notion_credentials(token: str) -> Tuple[bool, str, Optional[str]]:
    """Actively test Notion token by calling /v1/users/me to verify authenticity."""
    token_clean = token.strip()
    if not token_clean:
        return False, "Notion integration secret token cannot be empty.", None

    headers = get_notion_headers(token_clean)
    try:
        resp = requests.get(f"{NOTION_BASE_URL}/users/me", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bot_name = data.get("name") or (data.get("bot", {}).get("owner", {}).get("user", {}).get("name")) or "Notion Workspace"
            return True, f"Notion integration verified for '{bot_name}'.", bot_name
        elif resp.status_code == 401:
            return False, "Notion API rejected this token (401 Unauthorized). Please check that your secret token is copied accurately from notion.so/my-integrations.", None
        else:
            err_detail = resp.json().get("message", resp.text)
            return False, f"Notion API error ({resp.status_code}): {err_detail}", None
    except requests.exceptions.RequestException as req_err:
        return False, f"Could not reach Notion API servers: {req_err}", None


def search_notion(token: str, query: str = "") -> str:
    """Search pages and databases in the user's connected Notion workspace."""
    headers = get_notion_headers(token)
    payload = {"query": query, "page_size": 10}
    try:
        resp = requests.post(f"{NOTION_BASE_URL}/search", headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            return f"Notion API error ({resp.status_code}): {resp.text}"
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return f"No Notion pages or databases found matching '{query}'. Make sure you invited your Integration bot to the pages in Notion."

        summaries = []
        for item in results:
            obj_type = item.get("object", "page")
            item_id = item.get("id")
            title = "Untitled"
            props = item.get("properties", {})
            for p_name, p_val in props.items():
                if p_val.get("type") == "title":
                    title_list = p_val.get("title", [])
                    if title_list:
                        title = "".join(t.get("plain_text", "") for t in title_list)
                    break
            summaries.append(f"- [{obj_type.upper()}] Title: {title} (ID: {item_id})")

        return f"Found {len(results)} Notion items:\n" + "\n".join(summaries)
    except Exception as exc:
        return f"Failed to search Notion workspace: {exc}"


def read_notion_page_blocks(token: str, page_id: str) -> str:
    """Read block children / text content from a Notion page."""
    headers = get_notion_headers(token)
    clean_id = page_id.replace("-", "").strip()
    try:
        resp = requests.get(f"{NOTION_BASE_URL}/blocks/{clean_id}/children", headers=headers, timeout=10)
        if resp.status_code != 200:
            return f"Notion API error ({resp.status_code}): {resp.text}"
        data = resp.json()
        blocks = data.get("results", [])
        text_lines = []
        for block in blocks:
            b_type = block.get("type")
            b_content = block.get(b_type, {})
            rich_texts = b_content.get("rich_text", [])
            line = "".join(rt.get("plain_text", "") for rt in rich_texts)
            if line:
                text_lines.append(line)
        return "\n".join(text_lines) if text_lines else "Page has no text content."
    except Exception as exc:
        return f"Failed to read Notion page: {exc}"


def create_notion_page(token: str, title: str, content: str, parent_page_id: Optional[str] = None) -> str:
    """Create a new page in Notion."""
    headers = get_notion_headers(token)
    
    if not parent_page_id:
        try:
            search_resp = requests.post(f"{NOTION_BASE_URL}/search", headers=headers, json={"filter": {"value": "page", "property": "object"}}, timeout=10)
            if search_resp.status_code == 200:
                results = search_resp.json().get("results", [])
                if results:
                    parent_page_id = results[0]["id"]
        except Exception:
            pass

    parent_payload = {"page_id": parent_page_id} if parent_page_id else {"workspace": True}
    
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    children_blocks = []
    for p in paragraphs:
        children_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": p[:2000]}}]
            }
        })

    payload = {
        "parent": parent_payload,
        "properties": {
            "title": {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        },
        "children": children_blocks[:50]
    }

    try:
        resp = requests.post(f"{NOTION_BASE_URL}/pages", headers=headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            page_data = resp.json()
            return f"Status: Page Created Successfully\nTitle: {title}\nPage ID: {page_data.get('id')}\nSummary: {content[:150]}"
        return f"Notion API error ({resp.status_code}): {resp.text}"
    except Exception as exc:
        return f"Failed to create Notion page: {exc}"


def build_user_notion_tools(token: str):
    """Build LangChain tools bound to user's Notion token."""
    
    @tool
    def search_workspace(query: str = "") -> str:
        """Search pages and databases in the user's Notion workspace."""
        return search_notion(token, query)

    @tool
    def read_page(page_id: str) -> str:
        """Read the contents of a specific Notion page given its ID."""
        return read_notion_page_blocks(token, page_id)

    @tool
    def create_page(title: str, content: str, parent_page_id: str = "") -> str:
        """Create a new page in the user's Notion workspace with the given title and text content."""
        return create_notion_page(token, title, content, parent_page_id if parent_page_id else None)

    return [search_workspace, read_page, create_page]
