"""Per-agent configuration: defaults.yaml < agent folder config.yaml < AGENT_<NAME>_* env overrides."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

AGENTS_DIR = Path(__file__).parent
_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")

# Local runs keep secrets in .env; Docker injects real environment variables.
for _p in (Path.cwd() / ".env", Path.cwd().parent / ".env"):
    load_dotenv(_p, override=False)


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key_env: str = "NVIDIA_API_KEY"
    temperature: float = 0.2
    max_tokens: int = 8192
    timeout_s: float = 180.0
    max_retries: int = 3
    extra_body: dict | None = None

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()


@dataclass
class AgentConfig:
    name: str
    enabled: bool
    llm: LLMConfig
    title: str = ""
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.getenv(m.group(1)) or (m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}


def _as_bool(s: str) -> bool:
    return s.strip().lower() in ("1", "true", "yes", "on")


def load_agent_config(name: str) -> AgentConfig:
    folder = AGENTS_DIR / name
    raw = _expand(_merge(_read_yaml(AGENTS_DIR / "defaults.yaml"), _read_yaml(folder / "config.yaml")))
    llm = raw.get("llm", {})

    # Environment overrides, e.g. AGENT_TECHNICALS_MODEL=meta/llama-3.1-70b-instruct
    pre = f"AGENT_{name.upper()}_"
    for env, key, cast in (("MODEL", "model", str), ("BASE_URL", "base_url", str),
                           ("API_KEY_ENV", "api_key_env", str), ("TEMPERATURE", "temperature", float),
                           ("MAX_TOKENS", "max_tokens", int)):
        if os.getenv(pre + env):
            llm[key] = cast(os.environ[pre + env])
    enabled = _as_bool(os.environ[pre + "ENABLED"]) if os.getenv(pre + "ENABLED") else bool(raw.get("enabled", True))

    prompt_file = folder / "prompt.md"
    return AgentConfig(
        name=name,
        enabled=enabled,
        title=raw.get("title", name),
        description=raw.get("description", ""),
        params=raw.get("params", {}) or {},
        system_prompt=prompt_file.read_text(encoding="utf-8").strip() if prompt_file.exists() else "",
        llm=LLMConfig(**{k: llm[k] for k in LLMConfig.__dataclass_fields__ if k in llm}),
    )
