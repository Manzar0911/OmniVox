"""Builds the Orchestrator: a generalist agent that answers directly or
delegates to a specialist sub-agent (Notion, Gmail, or web research).

    Orchestrator -> notion_expert  (Notion MCP tools)
                -> email_expert   (Gmail MCP tools)
                -> researcher     (web search + summarize)

Each specialist is itself a full create_agent, wrapped as a plain tool so
the Orchestrator can call it like any other tool. This keeps each
specialist's tool access scoped to just the service it owns, and keeps
their system prompts focused on one job instead of one long prompt trying
to cover Gmail, Notion, and research at once.
"""
import asyncio
from typing import Optional
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from . import config
from .agents.email_expert import build_email_expert
from .agents.notion_expert import build_notion_expert
from .agents.researcher import build_researcher
from .logging_utils import log_stage

ORCHESTRATOR_SYSTEM_PROMPT = """You are OmniVox, a voice-controlled executive assistant.

Answer general questions directly yourself. For anything that needs real
access to the user's Notion workspace, Gmail inbox, or current web
information, delegate to the matching specialist tool instead of guessing:
- notion_expert: search, read, or create Notion pages.
- email_expert: check, search, draft, or send Gmail.
- researcher: look something up on the web and summarize it.

Chain specialists when a request needs more than one step - e.g. ask
researcher for a summary, then pass that summary to notion_expert to save
as a page.

STRUCTURED OUTPUT & VOICE RULES:
- Present all information in clean, structured, readable format.
- Do NOT use markdown asterisks (never output **bold** or *italic* asterisks).
- Do NOT output raw angle brackets (< >) or raw URLs.
- For emails: clearly present Sender, Subject, and Summary.
- For Notion: clearly present Status, Title, and Details.
- For Research: clearly present Topic, Key Findings, and Conclusion.
- Keep the overall response conversational and ready to be read aloud cleanly by the voice synthesizer.
- Report outcomes naturally - never mention internal mechanics like "tool" or "delegated".
"""




_SPECIALIST_BUILD_TIMEOUT = 20.0


async def _try_build(build_fn, name: str):
    """Build a specialist, but never let its failure - or hang - take down the others."""
    try:
        return await asyncio.wait_for(build_fn(), timeout=_SPECIALIST_BUILD_TIMEOUT)
    except TimeoutError:
        print(
            f"[agent] {name} timed out after {_SPECIALIST_BUILD_TIMEOUT}s during initialization "
            "(likely stuck waiting on an interactive auth flow) - it will report itself unavailable"
        )
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] {name} failed to initialize, it will report itself unavailable: {exc}")
        return None


async def build_agent():
    """Build the three specialists, wrap them as tools, and assemble the Orchestrator."""
    notion_agent = await _try_build(build_notion_expert, "notion_expert")
    email_agent = await _try_build(build_email_expert, "email_expert")
    research_agent = await _try_build(build_researcher, "researcher")


    @tool
    async def notion_expert(request: str, config: Optional[RunnableConfig] = None) -> str:
        """Delegate a Notion request (search, read, or create pages) to the Notion specialist."""
        if notion_agent is None:
            return "The Notion integration isn't available on this server right now."
        log_stage("Orchestrator -> notion_expert", input=request)
        result = await notion_agent.ainvoke({"messages": [HumanMessage(content=request)]}, config=config)
        output = result["messages"][-1].content
        log_stage("notion_expert -> Orchestrator", output=output)
        return output

    @tool
    async def email_expert(request: str, config: Optional[RunnableConfig] = None) -> str:
        """Delegate a Gmail request (check, search, draft, or send email) to the email specialist."""
        if email_agent is None:
            return "The Gmail integration isn't available on this server right now."
        log_stage("Orchestrator -> email_expert", input=request)
        result = await email_agent.ainvoke({"messages": [HumanMessage(content=request)]}, config=config)
        output = result["messages"][-1].content
        log_stage("email_expert -> Orchestrator", output=output)
        return output

    @tool
    async def researcher(topic: str, config: Optional[RunnableConfig] = None) -> str:
        """Delegate a web research request to the research specialist; returns a markdown summary."""
        if research_agent is None:
            return "The research tool isn't available on this server right now."
        log_stage("Orchestrator -> researcher", input=topic)
        result = await research_agent.ainvoke({"messages": [HumanMessage(content=topic)]}, config=config)
        output = result["messages"][-1].content
        log_stage("researcher -> Orchestrator", output=output)
        return output

    tools = [notion_expert, email_expert, researcher]
    return create_agent(config.get_chat_model(), tools=tools, system_prompt=ORCHESTRATOR_SYSTEM_PROMPT)

