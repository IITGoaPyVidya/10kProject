"""LLM access for agents: any OpenAI-compatible endpoint, configured per agent."""
import threading
from functools import lru_cache
from typing import Callable, Protocol

from openai import OpenAI

from app.agents.config import LLMConfig


class LLMError(RuntimeError):
    """The LLM call failed or returned nothing usable."""


class LLM(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str: ...


@lru_cache(maxsize=16)
def _client(base_url: str, api_key: str, timeout: float, retries: int) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=retries)


class OpenAICompatLLM:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.model = cfg.model

    def complete(self, system: str, user: str) -> str:
        if not self.cfg.api_key:
            raise LLMError(f"API key env var {self.cfg.api_key_env} is not set.")
        client = _client(self.cfg.base_url, self.cfg.api_key, self.cfg.timeout_s, self.cfg.max_retries)
        kwargs = {"extra_body": self.cfg.extra_body} if self.cfg.extra_body else {}
        try:
            resp = client.chat.completions.create(
                model=self.cfg.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens, stream=False, **kwargs)
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        choice = resp.choices[0]
        if not (choice.message.content or "").strip():
            raise LLMError(f"Model returned no content (finish_reason={choice.finish_reason}).")
        return choice.message.content


_factory: Callable[[LLMConfig], LLM] = OpenAICompatLLM
_lock = threading.Lock()


def make_llm(cfg: LLMConfig) -> LLM:
    return _factory(cfg)


def set_llm_factory(factory: Callable[[LLMConfig], LLM] | None) -> None:
    """Swap the LLM implementation (used by tests, or to plug in another provider SDK)."""
    global _factory
    with _lock:
        _factory = factory or OpenAICompatLLM
