"""
llm_service.py — Secondary layer: unified LLM client for generating
iframe title candidates when heuristics produce low confidence.
Supports Gemini, Claude, OpenAI/ChatGPT, DeepSeek, and Azure/Copilot.
"""
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

WCAG_PROMPT_TEMPLATE = """You are a Web Accessibility Specialist (WCAG 2.2 expert).

Your task: Generate 3 ranked, concise, descriptive `title` attribute values for an HTML <iframe>.
The title must allow a screen reader user to understand the purpose of the frame WITHOUT entering it.

Guidelines:
- Maximum 80 characters per title
- Do NOT start with "iframe" or "embedded frame"
- Be specific: describe PURPOSE and CONTENT, not just the platform
- Follow WCAG 2.2 SC 4.1.2 and Technique H64
- If the content cannot be determined, say so honestly

Context provided:
IFRAME HTML: {iframe_html}
SOURCE URL TITLE: {page_title}
SOURCE URL DESCRIPTION: {page_description}
SOURCE URL H1: {page_h1}
SURROUNDING DOM CONTEXT: {dom_context}

Respond ONLY with a valid JSON array of exactly 3 objects, no markdown, no explanation:
[
  {{"rank": 1, "title": "...", "rationale": "Brief WCAG rationale for this choice"}},
  {{"rank": 2, "title": "...", "rationale": "..."}},
  {{"rank": 3, "title": "...", "rationale": "..."}}
]"""


def _build_prompt(iframe_html: str, metadata: dict, dom_context: str | None) -> str:
    return WCAG_PROMPT_TEMPLATE.format(
        iframe_html=iframe_html[:500],
        page_title=metadata.get("title") or "N/A",
        page_description=metadata.get("description") or "N/A",
        page_h1=metadata.get("h1") or "N/A",
        dom_context=dom_context or "N/A",
    )


def _parse_response(raw: str) -> list[dict]:
    """Extract and parse JSON array from LLM response."""
    # Strip any markdown code fences
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        # Attempt to extract JSON array with regex
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return [{"rank": 1, "title": "Embedded Content", "rationale": "LLM response could not be parsed."}]


# ── Provider implementations ──────────────────────────────────────────────────

def _call_gemini(prompt: str) -> list[dict]:
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return _parse_response(response.text)


def _call_claude(prompt: str) -> list[dict]:
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set.")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_response(message.content[0].text)


def _call_openai(prompt: str) -> list[dict]:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    return _parse_response(response.choices[0].message.content)


def _call_deepseek(prompt: str) -> list[dict]:
    from openai import OpenAI
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set.")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    return _parse_response(response.choices[0].message.content)


def _call_azure(prompt: str) -> list[dict]:
    from openai import AzureOpenAI
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    if not api_key or not endpoint:
        raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set.")
    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version="2024-02-01",
    )
    response = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    return _parse_response(response.choices[0].message.content)


_PROVIDERS = {
    "gemini": _call_gemini,
    "claude": _call_claude,
    "openai": _call_openai,
    "deepseek": _call_deepseek,
    "azure": _call_azure,
}

# Fallback order when preferred provider has no key
_FALLBACK_ORDER = ["gemini", "claude", "openai", "deepseek", "azure"]


def generate_titles(
    iframe_html: str,
    metadata: dict,
    dom_context: str | None,
    provider: str | None = None,
) -> dict:
    """
    Generate 3 ranked title candidates using the specified (or default) LLM provider.
    Falls back through providers if the preferred one has no key set.

    Returns:
        {
            "candidates": [...],
            "provider_used": str,
            "error": str | None
        }
    """
    prompt = _build_prompt(iframe_html, metadata, dom_context)
    preferred = provider or os.getenv("DEFAULT_LLM_PROVIDER", "gemini")

    order = [preferred] + [p for p in _FALLBACK_ORDER if p != preferred]

    last_error = None
    for prov in order:
        fn = _PROVIDERS.get(prov)
        if not fn:
            continue
        try:
            candidates = fn(prompt)
            return {"candidates": candidates, "provider_used": prov, "error": None}
        except ValueError as e:
            # Missing key — try next provider
            last_error = str(e)
            continue
        except Exception as e:
            last_error = str(e)
            break  # API error, don't keep trying

    return {
        "candidates": [
            {"rank": 1, "title": "Embedded Content", "rationale": "No LLM provider was available or an API error occurred."}
        ],
        "provider_used": None,
        "error": last_error,
    }
