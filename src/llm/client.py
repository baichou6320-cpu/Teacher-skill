"""LLM 通信封装.

Supports both Anthropic Messages API and OpenAI-compatible chat-completions
providers such as Kimi/Moonshot and DeepSeek.
"""
import os
from typing import Optional

import httpx
from anthropic import Anthropic, AuthenticationError, PermissionDeniedError, RateLimitError

from src.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from src.utils.config import get_config
from src.utils.logger import get_logger


class LLMClient:
    """LLM client wrapper with retry and multi-provider support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        cfg = get_config().llm
        self.logger = get_logger("llm")

        self.provider = cfg.provider
        self.api_format = cfg.api_format
        self.api_key = api_key or self._read_api_key()
        if not self.api_key:
            raise ValueError("API key is required")

        self.model_id = model_id or cfg.model_id
        self.base_url = (
            base_url
            or os.getenv("TEACHER_SKILL_BASE_URL")
            or os.getenv("ANTHROPIC_BASE_URL")
            or cfg.base_url
        )
        self.max_retries = cfg.retry_count

        self.client: Anthropic | None = None
        if self.api_format == "anthropic":
            kwargs: dict = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self.client = Anthropic(**kwargs)
        elif self.api_format != "openai":
            raise ValueError(f"Unsupported llm.api_format: {self.api_format}")

        self.logger.debug(
            f"LLMClient initialized: provider={self.provider}, "
            f"api_format={self.api_format}, model={self.model_id}"
        )

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate a response with automatic retry.

        For models that return thinking blocks (e.g. Kimi), the official text
        output is preferred and thinking content is used as a fallback.
        """
        import time

        cfg = get_config().llm
        model = model or self.model_id
        max_tokens = max_tokens if max_tokens is not None else cfg.max_tokens
        temperature = temperature if temperature is not None else cfg.temperature
        last_error: Optional[Exception] = None

        self.logger.info(
            f"LLM call start: provider={self.provider}, api_format={self.api_format}, "
            f"model={model}, max_tokens={max_tokens}, sys_prompt_len={len(system_prompt)}, "
            f"user_msg_len={len(user_message)}"
        )
        start_time = time.time()

        timeout = cfg.timeout

        for attempt in range(self.max_retries):
            try:
                if self.api_format == "anthropic":
                    text = self._generate_anthropic(
                        model=model,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                    )
                else:
                    text = self._generate_openai_compatible(
                        model=model,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                    )
                elapsed = time.time() - start_time
                self.logger.info(
                    f"LLM call success: attempt={attempt + 1}, elapsed={elapsed:.2f}s, "
                    f"response_len={len(text)}"
                )
                return text
            except (AuthenticationError, PermissionDeniedError) as exc:
                self.logger.error(f"LLM auth error: {exc}")
                raise LLMAuthError(
                    "API Key 无效或服务不可用，请检查 .env 中的 TEACHER_SKILL_API_KEY 配置"
                ) from exc
            except RateLimitError as exc:
                self.logger.warning(f"LLM rate limit: {exc}")
                if attempt == self.max_retries - 1:
                    raise LLMRateLimitError(
                        "请求过于频繁，请稍后再试"
                    ) from exc
                # 指数退避：1s, 2s, 4s...
                delay = 2 ** attempt
                self.logger.info(f"Rate limit, backing off for {delay}s")
                time.sleep(delay)
            except httpx.TimeoutException as exc:
                self.logger.warning(f"LLM timeout (attempt {attempt + 1}): {exc}")
                if attempt == self.max_retries - 1:
                    raise LLMTimeoutError(
                        "LLM 响应超时，请检查网络连接或稍后重试"
                    ) from exc
            except httpx.ConnectError as exc:
                self.logger.warning(f"LLM connection error (attempt {attempt + 1}): {exc}")
                if attempt == self.max_retries - 1:
                    raise LLMConnectionError(
                        "网络连接失败，请检查网络连接后重试"
                    ) from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                self.logger.warning(
                    f"LLM HTTP error (attempt {attempt + 1}): status={status_code}, {exc}"
                )
                if status_code in (401, 403):
                    raise LLMAuthError(
                        "API Key 无效或服务不可用，请检查 .env 中的 TEACHER_SKILL_API_KEY 配置"
                    ) from exc
                if status_code == 429:
                    if attempt == self.max_retries - 1:
                        raise LLMRateLimitError("请求过于频繁，请稍后再试") from exc
                    delay = 2 ** attempt
                    self.logger.info(f"Rate limit, backing off for {delay}s")
                    time.sleep(delay)
                    continue
                if attempt == self.max_retries - 1:
                    raise LLMResponseError(
                        f"LLM 服务返回错误：HTTP {status_code}"
                    ) from exc
            except Exception as exc:
                self.logger.warning(f"LLM call attempt {attempt + 1} failed: {exc}")
                if attempt == self.max_retries - 1:
                    self.logger.error(f"LLM call failed after {self.max_retries} retries")
                    raise LLMResponseError(
                        f"LLM 调用失败: {exc}"
                    ) from exc

        # Should never reach here, but keeps type-checker happy
        return ""

    @staticmethod
    def _read_api_key() -> str | None:
        """Read the API key from new generic vars, then legacy/provider vars."""

        return (
            os.getenv("TEACHER_SKILL_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("MOONSHOT_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
        )

    def _generate_anthropic(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> str:
        """Generate with the Anthropic Messages API."""

        if self.client is None:
            raise ValueError("Anthropic client is not initialized")

        response = self.client.messages.create(
            model=model,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_message}],
            timeout=timeout,
        )
        return self._extract_text(response)

    def _generate_openai_compatible(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> str:
        """Generate with an OpenAI-compatible chat-completions endpoint."""

        if not self.base_url:
            raise ValueError("OpenAI-compatible providers require llm.base_url")

        url = self._chat_completions_url(self.base_url)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("LLM 响应格式异常，未找到 choices[0].message.content") from exc
        return "" if content is None else str(content)

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        """Return the full chat-completions URL for an OpenAI-compatible API."""

        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return normalized + "/chat/completions"

    @staticmethod
    def _extract_text(response) -> str:
        """Extract usable text from an Anthropic Messages API response.

        Priority:
        1. type='text' blocks with non-empty content
        2. type='thinking' blocks (fallback)
        3. Any block with a .text attribute (last resort)
        """
        text_parts: list[str] = []
        thinking_parts: list[str] = []

        for block in response.content:
            block_type = getattr(block, "type", None)

            if block_type == "text":
                t = getattr(block, "text", "")
                if t and t.strip():
                    text_parts.append(t)
            elif block_type == "thinking":
                t = getattr(block, "thinking", "")
                if t and t.strip():
                    thinking_parts.append(t)
            else:
                # Last resort: try .text attribute on unknown block types
                t = getattr(block, "text", None)
                if t and t.strip():
                    text_parts.append(t)

        if text_parts:
            return "\n".join(text_parts)
        if thinking_parts:
            return "\n".join(thinking_parts)
        return ""

    @staticmethod
    def interpolate(template: str, variables: dict[str, object]) -> str:
        """Replace {{variable}} placeholders in a template string.

        Example:
            >>> LLMClient.interpolate("Hello {{name}}!", {"name": "World"})
            'Hello World!'
        """
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
