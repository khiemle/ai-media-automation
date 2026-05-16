"""Canned LLM responses (Gemini, Ollama)."""
from __future__ import annotations


def gemini_text_response(text: str = "ok") -> dict:
    """Shape returned by google-genai's `generate_content` (.text accessor)."""
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
                "finish_reason": "STOP",
            }
        ],
        "usage_metadata": {
            "prompt_token_count": 10,
            "candidates_token_count": 5,
            "total_token_count": 15,
        },
    }


def ollama_chat_response(content: str = "ok", model: str = "qwen2.5") -> dict:
    """Shape returned by Ollama's /api/chat endpoint."""
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "total_duration": 1_000_000,
        "eval_count": 5,
    }
