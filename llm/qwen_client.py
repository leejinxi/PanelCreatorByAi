from time import perf_counter
from typing import List, Optional

import requests
from langchain_core.language_models.llms import LLM

from agent.execution_trace import record_llm


class LocalQwenError(RuntimeError):
    """本地模型调用失败的统一异常。"""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable


class LocalQwen(LLM):
    model_name: str = "qwen2.5:7b"
    url: str = (
        "http://localhost:11434/api/chat"
    )
    temperature: float = 0.0


    @property
    def _llm_type(self) -> str:
        return "local_qwen"


    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
            },
        }

        started = perf_counter()
        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise LocalQwenError(
                "本地模型请求超时。",
                error_code="LLM_TIMEOUT",
                retryable=True,
            ) from exc
        except requests.ConnectionError as exc:
            raise LocalQwenError(
                "无法连接本地模型服务。",
                error_code="LLM_UNAVAILABLE",
                retryable=True,
            ) from exc
        except requests.HTTPError as exc:
            status_code = (
                exc.response.status_code
                if exc.response is not None
                else None
            )
            raise LocalQwenError(
                f"本地模型服务返回 HTTP 错误：{status_code or 'unknown'}。",
                error_code="LLM_HTTP_ERROR",
                retryable=status_code is not None and status_code >= 500,
            ) from exc
        except requests.RequestException as exc:
            raise LocalQwenError(
                "本地模型请求失败。",
                error_code="LLM_REQUEST_ERROR",
            ) from exc
        finally:
            record_llm(round((perf_counter() - started) * 1000))

        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LocalQwenError(
                "本地模型响应缺少有效内容。",
                error_code="LLM_INVALID_RESPONSE",
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise LocalQwenError(
                "本地模型响应内容为空。",
                error_code="LLM_EMPTY_RESPONSE",
            )

        return content
