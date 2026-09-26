"""Builds user-scoped Orchestrator and specialist agents based on active user integrations with full LangSmith trace nesting."""
import asyncio
from typing import Dict, List, Optional

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import config
from .agents.researcher import build_researcher
from .db.models import UserIntegration
from .logging_utils import log_stage
from .tools.gmail_dynamic import build_user_gmail_tools
from .tools.notion_dynamic import build_user_notion_tools
from .tools.research_tool import research_topic

ORCHESTRATOR_SYSTEM_PROMPT = """You are OmniVox, a personalized voice-controlled executive assistant.

Answer general questions directly yourself. For anything that needs real
access to the user's Notion workspace, Gmail inbox, or current web
information, delegate to the matching specialist tool:
- notion_expert: search, read, or create Notion pages.
- email_expert: check, search, draft, or send Gmail.
- researcher: look something up on the web and summarize it.

Chain specialists when a request needs more than one step (e.g. research a topic, then save it to Notion).

STRUCTURED OUTPUT & VOICE RULES:
- Present all information in clean, structured, readable format.
- Do NOT use markdown asterisks (never output **bold** or *italic* asterisks).
- Do NOT output raw angle brackets (< >) or raw URLs.
- For emails: clearly present Sender, Subject, and Summary.
- For Notion: clearly present Status, Title, and Details.
- For Research: clearly present Topic, Key Findings, and Conclusion.
- Keep the overall response conversational and ready to be read aloud cleanly by the voice synthesizer.
"""


async def get_user_integrations(db: AsyncSession, user_id: int) -> Dict[str, UserIntegration]:
    """Retrieve all active integrations for a user."""
    stmt = select(UserIntegration).where(
        UserIntegration.user_id == user_id,
        UserIntegration.is_active == True
    )
    result = await db.execute(stmt)
    integrations = result.scalars().all()
    return {integ.provider.lower(): integ for integ in integrations}


async def build_user_agent(db: Optional[AsyncSession] = None, user_id: Optional[int] = None):
    """Build an orchestrator agent dynamically scoped to the user's connected Gmail and Notion accounts."""
    user_integrations: Dict[str, UserIntegration] = {}
    if db is not None and user_id is not None:
        try:
            user_integrations = await get_user_integrations(db, user_id)
        except Exception as exc:
            print(f"[user_agent] Failed to load integrations for user {user_id}: {exc}")

    # 1. Notion Specialist
    notion_integ = user_integrations.get("notion")
    if notion_integ and notion_integ.credentials_json:
        notion_tools = build_user_notion_tools(notion_integ.credentials_json)
        notion_subagent = create_agent(
            config.get_chat_model(),
            tools=notion_tools,
            system_prompt="You are the Notion specialist. Use tools to search, read, and create pages in the user's workspace.",
        )
    else:
        notion_subagent = None

    # 2. Gmail Specialist
    gmail_integ = user_integrations.get("gmail")
    if gmail_integ and gmail_integ.credentials_json:
        gmail_tools = build_user_gmail_tools(gmail_integ.credentials_json)
        gmail_subagent = create_agent(
            config.get_chat_model(),
            tools=gmail_tools,
            system_prompt="You are the Gmail specialist. Use tools to search, read, draft, and send emails for the user.",
        )
    else:
        gmail_subagent = None

    # 3. Researcher Specialist
    research_agent = await build_researcher()

    @tool
    async def notion_expert(request: str, config: Optional[RunnableConfig] = None) -> str:
        """Delegate a Notion request (search, read, or create pages) to the user's Notion workspace."""
        if notion_subagent is None:
            return "You have not connected your Notion account yet. You can link your Notion integration token in the Integrations settings."
        log_stage("Orchestrator -> notion_expert (User)", input=request)
        result = await notion_subagent.ainvoke({"messages": [HumanMessage(content=request)]}, config=config)
        output = result["messages"][-1].content
        log_stage("notion_expert -> Orchestrator", output=output)
        return output

    @tool
    async def email_expert(request: str, config: Optional[RunnableConfig] = None) -> str:
        """Delegate a Gmail request (search, read, draft, send) to the user's Gmail inbox."""
        if gmail_subagent is None:
            return "You have not connected your Gmail account yet. You can connect your Gmail account via Google OAuth in the Integrations settings."
        log_stage("Orchestrator -> email_expert (User)", input=request)
        result = await gmail_subagent.ainvoke({"messages": [HumanMessage(content=request)]}, config=config)
        output = result["messages"][-1].content
        log_stage("email_expert -> Orchestrator", output=output)
        return output

    @tool
    async def researcher(topic: str, config: Optional[RunnableConfig] = None) -> str:
        """Delegate a web research request to the research specialist."""
        log_stage("Orchestrator -> researcher", input=topic)
        result = await research_agent.ainvoke({"messages": [HumanMessage(content=topic)]}, config=config)
        output = result["messages"][-1].content
        log_stage("researcher -> Orchestrator", output=output)
        return output

    tools = [notion_expert, email_expert, researcher]
    return create_agent(config.get_chat_model(), tools=tools, system_prompt=ORCHESTRATOR_SYSTEM_PROMPT)
