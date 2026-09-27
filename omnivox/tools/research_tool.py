import os
import re
from typing import Optional
import requests
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .. import config as app_config
from ..cache import search_cache
from ..guardrails import guardrails_manager
from ..logging_utils import log_stage


def _clean_for_voice(text: str) -> str:
    """Strip markdown asterisks, raw URLs, and markdown links to keep output clean and voice-ready."""
    text = text.replace("**", "").replace("*", "")
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    return text.strip()


def _format_tavily_results(topic: str, answer: Optional[str], results: list) -> str:
    """Format Tavily real-time results into a structured voice-ready output."""
    lines = [f"Topic: {topic}", "Key Findings:"]

    if answer:
        cleaned_ans = _clean_for_voice(answer)
        sentences = [s.strip() for s in cleaned_ans.split("\n") if s.strip()]
        for s in sentences[:4]:
            if not s.startswith("-"):
                lines.append(f"- {s}")
            else:
                lines.append(s)
    elif results:
        for r in results[:4]:
            content = _clean_for_voice(r.get("content", "") or r.get("title", ""))
            if content:
                if len(content) > 180:
                    content = content[:177] + "..."
                lines.append(f"- {content}")
    else:
        lines.append("- No recent live information found for this query.")

    if results and len(results) > 0:
        first_title = _clean_for_voice(results[0].get("title", topic))
        lines.append(f"Conclusion: Real-time web findings gathered regarding {first_title}.")
    else:
        lines.append("Conclusion: Research completed.")

    return "\n".join(lines)


def _perform_live_search(topic: str) -> str:
    """Execute live web search via Tavily API with DuckDuckGo fallback."""
    tavily_api_key = app_config.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY")

    if tavily_api_key:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_api_key,
                    "query": topic,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "max_results": 5,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer")
                results = data.get("results", [])
                output = _format_tavily_results(topic, answer, results)
                log_stage("Tavily -> researcher", output=output)
                return output
            else:
                print(f"[research_tool] Tavily API returned status {resp.status_code}: {resp.text}")
        except Exception as exc:
            print(f"[research_tool] Tavily search failed: {exc}")

    # Fallback to DuckDuckGo live search if Tavily key is missing or fails
    try:
        from duckduckgo_search import DDGS

        ddgs = DDGS()
        raw_results = list(ddgs.text(topic, max_results=5))
        results = [{"title": r.get("title", ""), "content": r.get("body", "")} for r in raw_results]
        output = _format_tavily_results(topic, None, results)
        log_stage("DuckDuckGo (fallback) -> researcher", output=output)
        return output
    except Exception as exc:
        print(f"[research_tool] DuckDuckGo fallback search failed: {exc}")

    fallback_msg = f"Topic: {topic}\nKey Findings:\n- Live search unavailable. Please ensure TAVILY_API_KEY is configured in your environment.\nConclusion: Web search could not be executed."
    log_stage("Tavily -> researcher", output=fallback_msg)
    return fallback_msg


@tool
def research_topic(topic: str, config: Optional[RunnableConfig] = None) -> str:
    """Research, analyze, and synthesize real-time, up-to-date web knowledge on a topic using Tavily Search with intelligent caching.

    Use this to search the live web for current events, updated news, real-time facts,
    or before creating a Notion page or answering executive questions.
    """
    # Guardrail input validation on research topic
    guard_res = guardrails_manager.validate_input(topic)
    if not guard_res.is_safe:
        return f"Topic: {topic}\nKey Findings:\n- {guard_res.reason}\nConclusion: Search request blocked by safety guardrails."

    cleaned_topic = guard_res.sanitized_text

    # Check search cache with in-flight deduplication
    cached_output = search_cache.get(cleaned_topic)
    if cached_output:
        log_stage("SearchCache -> researcher (HIT)", topic=cleaned_topic)
        return cached_output

    log_stage("researcher -> Tavily (MISS)", input=cleaned_topic)
    output = search_cache.get_or_compute(cleaned_topic, _perform_live_search, ttl_seconds=3600)

    # Output guardrail validation
    out_res = guardrails_manager.validate_output(output)
    return out_res.sanitized_text





