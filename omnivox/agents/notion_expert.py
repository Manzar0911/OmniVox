"""The Notion specialist sub-agent: owns the Notion MCP tools exclusively."""
from langchain.agents import create_agent

from .. import config
from ..mcp_client import mcp_client

SYSTEM_PROMPT = """You are the Notion specialist on a team of AI assistants.

You have direct tool access to the user's Notion workspace: searching,
reading, and creating pages. Handle whatever Notion request you're given
using those tools.

STRUCTURED OUTPUT RULES:
- Never use markdown asterisks (do NOT use **bold** or *italic* asterisks).
- Return cleanly structured responses following these standard schemas:

For Page / Item Creation:
Status: Page Created Successfully
Title: [Page Title]
Summary: [1-2 sentences on what was documented or amended]

For Search / Read Pages:
Status: [Found X Pages / Page Content Retrieved]
Title: [Page Title]
Details: [Clean summary of the page contents]
"""



async def build_notion_expert():
    """Discover the Notion MCP tools and assemble the specialist agent."""
    notion_tools = await mcp_client.get_tools(server_name="notion")
    return create_agent(config.get_chat_model(), tools=notion_tools, system_prompt=SYSTEM_PROMPT)
