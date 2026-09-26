from __future__ import annotations

import os


class BackendUnavailable(RuntimeError):
    pass


class LLMBackend:
    """Thin provider-agnostic chat wrapper.

    provider: anthropic | openai | openai_compatible
    """

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.0,
    ) -> None:
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        if provider == "anthropic":
            self.model = model or os.environ.get("RASHOMON_MODEL", "claude-haiku-4-5")
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise BackendUnavailable(
                    "ANTHROPIC_API_KEY is not set (needed for --backend llm). "
                    "Use --backend file for a recorded run, or --backend heuristic for probes."
                )
        elif provider in ("openai", "openai_compatible"):
            self.model = model or os.environ.get("RASHOMON_MODEL", "gpt-4o-mini")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
            if not self.api_key and provider == "openai":
                raise BackendUnavailable(
                    "OPENAI_API_KEY is not set (needed for --backend llm). "
                    "Use --backend file for a recorded run."
                )
        else:
            raise BackendUnavailable(f"unknown provider {provider!r}")

    def complete(self, system: str, user: str) -> str:
        if self.provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

        import openai

        kwargs = {"api_key": self.api_key}
        if getattr(self, "base_url", None):
            kwargs["base_url"] = self.base_url
        client = openai.OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()
