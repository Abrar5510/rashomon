from __future__ import annotations

import os


class BackendUnavailable(RuntimeError):
    pass


def resolve_provider() -> str:
    """Pick the first provider with a key in the environment."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    raise BackendUnavailable(
        "no API key found (set ANTHROPIC_API_KEY, OPENAI_API_KEY or GOOGLE_API_KEY). "
        "Use --backend file for a recorded run, or --backend heuristic for probes."
    )


class LLMBackend:
    """Thin provider-agnostic chat wrapper.

    provider: anthropic | openai | openai_compatible | gemini | auto
    """

    def __init__(
        self,
        provider: str = "auto",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.0,
    ) -> None:
        if provider in ("auto", "", None):
            provider = resolve_provider()
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
        elif provider in ("gemini", "google"):
            self.provider = "gemini"
            # flash-lite: the flagship 3.8-flash has a 20 req/day free quota;
            # lite has a much larger bucket. Override with RASHOMON_MODEL.
            self.model = model or os.environ.get("RASHOMON_MODEL", "gemini-3.5-flash-lite")
            self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not self.api_key:
                raise BackendUnavailable(
                    "GOOGLE_API_KEY / GEMINI_API_KEY is not set (needed for --backend llm). "
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

        if self.provider == "gemini":
            return self._complete_gemini(system, user)

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

    def _complete_gemini(self, system: str, user: str) -> str:
        import time

        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=self.api_key)
        cfg = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        transient = {429, 500, 502, 503, 504}
        last: Exception | None = None
        for attempt in range(5):
            try:
                resp = client.models.generate_content(model=self.model, contents=user, config=cfg)
                text = resp.text
                if not text:
                    raise RuntimeError(f"gemini returned no text (finish_reason={resp.candidates[0].finish_reason if resp.candidates else '?'})")
                return text
            except Exception as exc:  # noqa: BLE001 - retry on rate limits / flaky transport
                code = getattr(exc, "code", None)
                retriable = code in transient or code is None or any(
                    s in str(exc).lower() for s in ("429", "rate limit", "resource_exhausted", "overloaded", "deadline", "unavailable")
                )
                last = exc
                if not retriable or attempt == 4:
                    raise
                time.sleep(2 * (2**attempt))  # 2, 4, 8, 16 s
        raise last if last else RuntimeError("gemini request failed")


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()
