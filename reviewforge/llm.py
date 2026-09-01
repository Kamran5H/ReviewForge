"""One interface to whatever language model does the judgement steps.

The framework does deterministic work in code; the *reasoning* — drafting a section from
evidence, proposing and attacking a thesis, classifying a paper by reading it — is delegated
here. Backends: a local Ollama server, any OpenAI-compatible endpoint, or the Anthropic API.
The key is read from a file named in the config, never inlined, and never committed to the
data deposit.
"""
from __future__ import annotations
import json
import urllib.request
from pathlib import Path

from .config import LLMConfig


class LLM:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.key = ""
        if cfg.api_key_file and Path(cfg.api_key_file).exists():
            self.key = Path(cfg.api_key_file).read_text(encoding="utf-8").strip()

    def complete(self, system: str, user: str) -> str:
        b = self.cfg.backend
        if b == "none":
            return ("[LLM backend is 'none'. This stage needs a model. Set llm.backend in "
                    "config.yaml to ollama / openai / anthropic.]")
        if b == "ollama":
            return self._ollama(system, user)
        if b == "openai":
            return self._openai(system, user)
        if b == "anthropic":
            return self._anthropic(system, user)
        raise ValueError(f"unknown backend {b!r}")

    def _post(self, url: str, payload: dict, headers: dict) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())

    def _ollama(self, system, user):
        d = self._post(f"{self.cfg.base_url}/api/chat", {
            "model": self.cfg.model, "stream": False,
            "options": {"temperature": self.cfg.temperature},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}, {})
        return d.get("message", {}).get("content", "")

    def _openai(self, system, user):
        d = self._post(f"{self.cfg.base_url}/v1/chat/completions", {
            "model": self.cfg.model, "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]},
            {"Authorization": f"Bearer {self.key}"})
        return d["choices"][0]["message"]["content"]

    def _anthropic(self, system, user):
        d = self._post("https://api.anthropic.com/v1/messages", {
            "model": self.cfg.model, "max_tokens": self.cfg.max_tokens,
            "temperature": self.cfg.temperature, "system": system,
            "messages": [{"role": "user", "content": user}]},
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in d.get("content", []))
