"""Small synchronous provider interface; no retries, SDK telemetry or prompt logging."""

from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings


class ProviderFailure(Exception):
    def __init__(self, code: str, result=None):
        self.code = code
        self.result = result


@dataclass
class ModelReply:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class ModelProvider(Protocol):
    def complete(
        self, messages: list[dict[str, str]], *, json_output: bool = False
    ) -> ModelReply: ...


class MockProvider:
    def complete(self, messages, *, json_output=False):
        if json_output:
            from app.memory.context import CONTEXT_MARKER, mock_memory_answer
            from app.memory.extractor import mock_envelope

            content = (
                mock_memory_answer(messages)
                if CONTEXT_MARKER in messages[0]["content"]
                else mock_envelope(messages[-1]["content"])
            )
            from app.tasks.intent import TASK_MARKER, mock_task_output

            if TASK_MARKER in messages[0]["content"]:
                content = mock_task_output(messages, content)
            return ModelReply(content, "mock-v1", 0, 0)
        return ModelReply(
            "【Mock 测试回复】已收到你的消息；这不是 DeepSeek 的真实回答。", "mock-v1", 0, 0
        )


class Usage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class DeepSeekProvider:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def complete(self, messages, *, json_output=False):
        key = self.settings.deepseek_api_key.get_secret_value()
        if not key.strip():
            raise ProviderFailure("MODEL_NOT_CONFIGURED")
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(25, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(
                    f"{self.settings.deepseek_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": self.settings.deepseek_model,
                        "messages": messages,
                        "max_tokens": self.settings.deepseek_max_output_tokens,
                        "thinking": {"type": "disabled"},
                        "stream": False,
                        **({"response_format": {"type": "json_object"}} if json_output else {}),
                    },
                )
            if response.status_code != 200:
                raise ProviderFailure(f"MODEL_HTTP_{response.status_code}")
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = Usage.model_validate(data["usage"])
            if not isinstance(content, str) or len(content) > 20000:
                raise ValueError("Invalid reply")
            result = ModelReply(
                content,
                str(data.get("model", self.settings.deepseek_model))[:80],
                usage.prompt_tokens,
                usage.completion_tokens,
            )
            if not content.strip():
                raise ProviderFailure("MODEL_EMPTY_RESPONSE", result)
            return result
        except httpx.TimeoutException:
            raise ProviderFailure("MODEL_TIMEOUT_UNKNOWN") from None
        except httpx.RequestError:
            raise ProviderFailure("MODEL_NETWORK_UNKNOWN") from None
        except (ValueError, KeyError, IndexError, TypeError, ValidationError):
            raise ProviderFailure("MODEL_INVALID_RESPONSE_UNKNOWN") from None


def get_provider(settings: Settings) -> ModelProvider:
    return MockProvider() if settings.llm_provider == "mock" else DeepSeekProvider(settings)
