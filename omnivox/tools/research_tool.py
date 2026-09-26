"""Research tool powered directly by Qwen 2.5 7B for OmniVox."""
from langchain_core.tools import tool

from .. import config
from ..logging_utils import log_stage


@tool
def research_topic(topic: str) -> str:
    """Research, analyze, and synthesize in-depth knowledge on a topic using Qwen 2.5.

    Use this before creating a Notion page or answering executive questions whenever
    the user asks to research, explain, structure, or investigate a topic.
    """
    log_stage("researcher -> Qwen 2.5", input=topic)

    prompt = (
        "You are an expert research specialist. Conduct a comprehensive, highly accurate, "
        "and well-structured investigation on the following topic.\n\n"
        f"Topic: {topic}\n\n"
        "Instructions:\n"
        "- Format the output cleanly with clear sections: Topic, Key Findings, and Conclusion.\n"
        "- Do NOT use markdown asterisks (no **bold** or *italic* asterisks).\n"
        "- Use concise bullet points (- item).\n"
        "- Keep the response sharp, factual, and under 250 words.\n"
        "- Return only the structured content ready to be read aloud or saved into Notion."
    )

    llm = config.get_chat_model(temperature=0.3)
    response = llm.invoke(prompt)
    output = response.content if hasattr(response, "content") else str(response)
    log_stage("Qwen 2.5 -> researcher", output=output)
    return output

