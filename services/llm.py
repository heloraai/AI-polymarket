"""LLM 调用工具 — 支持 DeepSeek (Web) 和 Anthropic (CLI)"""

import json

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def get_deepseek_client() -> OpenAI:
    """获取 DeepSeek 客户端（Web 模式）。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def call_llm(
    client: OpenAI,
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 1024,
) -> str:
    """调用 LLM 并返回文本响应。"""
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        max_tokens=max_tokens,
        messages=full_messages,
    )
    return response.choices[0].message.content


def parse_json_from_text(text: str) -> dict:
    """从 LLM 响应文本中提取 JSON 对象。"""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {}


def build_transcript_context(transcript: list[dict]) -> str:
    """将辩论记录格式化为可读文本。"""
    if not transcript:
        return ""
    lines = []
    for msg in transcript:
        phase_label = msg.get("phase", "")
        agent = msg.get("agent_emoji", "") + msg.get("agent_name", "")
        target = ""
        if msg.get("target_agent"):
            target = f" (回应 @{msg['target_agent']})"
        lines.append(f"[{phase_label}] {agent}{target}: {msg.get('content', '')}")
    return "\n".join(lines)
