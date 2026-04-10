from __future__ import annotations
import os
from crewai import LLM

# Toggle: set USE_LOCAL=false in .env to use Gemini instead of Ollama
_use_local = os.getenv("USE_LOCAL", "true").lower() != "false"

if _use_local:
    # Ollama local models (default)
    # General purpose model for text generation
    llm_general = LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")

    # Reasoning model for complex analysis
    llm_reasoning = LLM(model="ollama/gemma3:4b", base_url="http://localhost:11434")

    # Vision model for multimodal tasks (image + text)
    llm_vision = LLM(model="ollama/llava", base_url="http://localhost:11434")
else:
    # Gemini cloud models — set GEMINI_API_KEY, GEMINI_MODEL, GEMINI_REASONING_MODEL in .env
    _api_key = os.getenv("GEMINI_API_KEY")
    llm_general = LLM(
        model=os.getenv("GEMINI_MODEL", "gemini/gemini-2.0-flash-001"),
        api_key=_api_key,
        temperature=0,
        max_tokens=4096,
    )
    llm_reasoning = LLM(
        model=os.getenv("GEMINI_REASONING_MODEL", "gemini/gemini-2.5-flash-preview-04-17"),
        api_key=_api_key,
        temperature=0,
        max_tokens=4096,
    )
    llm_vision = llm_reasoning  # Use reasoning model for vision tasks with Gemini