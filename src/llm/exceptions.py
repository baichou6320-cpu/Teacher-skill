"""LLM 相关异常定义

提供具体的异常类型，让上层能根据错误原因给出不同的用户提示。
"""


class LLMError(Exception):
    """LLM 调用异常的基类."""
    pass


class LLMTimeoutError(LLMError):
    """LLM 请求超时.

    通常由网络延迟或服务端响应慢导致。建议重试。
    """
    pass


class LLMConnectionError(LLMError):
    """网络连接失败.

    断网、DNS 解析失败、服务端不可达等。建议检查网络后重试。
    """
    pass


class LLMAuthError(LLMError):
    """API 认证失败.

    API Key 无效、账号欠费、无权限访问该模型。不会重试，需用户检查配置。
    """
    pass


class LLMRateLimitError(LLMError):
    """请求频率被限制.

    发送请求过快，服务端返回 429。建议带退避延迟后重试。
    """
    pass


class LLMResponseError(LLMError):
    """LLM 返回了无法处理的响应.

    服务端返回了非预期的状态码或格式。可尝试重试。
    """
    pass
