"""LLM 通信封装

支持 Anthropic 兼容接口（Claude、Kimi、MiniMax、GLM、DeepSeek 等）
"""
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

        self.api_key = api_key
        if not self.api_key:
            import os
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        self.model_id = model_id or cfg.model_id
        self.base_url = base_url
        if not self.base_url:
            import os
            self.base_url = os.getenv("ANTHROPIC_BASE_URL")
        self.max_retries = cfg.retry_count

        # Initialise Anthropic client (with optional custom base_url)
        kwargs: dict = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = Anthropic(**kwargs)
        self.logger.debug("LLMClient initialized")

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
            f"LLM call start: model={model}, max_tokens={max_tokens}, "
            f"sys_prompt_len={len(system_prompt)}, user_msg_len={len(user_message)}"
        )
        start_time = time.time()

        timeout = cfg.timeout

        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    system=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": user_message}],
                    timeout=timeout,
                )
                text = self._extract_text(response)
                elapsed = time.time() - start_time
                self.logger.info(
                    f"LLM call success: attempt={attempt + 1}, elapsed={elapsed:.2f}s, "
                    f"response_len={len(text)}"
                )
                return text
            except (AuthenticationError, PermissionDeniedError) as exc:
                self.logger.error(f"LLM auth error: {exc}")
                raise LLMAuthError(
                    "API Key 无效或服务不可用，请检查 .env 中的 ANTHROPIC_API_KEY 配置"
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
