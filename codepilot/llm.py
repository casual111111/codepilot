import asyncio

from codepilot.config import CodePilotConfig


class LLMError(Exception):
    pass


class LLMClient:
    """
    OpenAI-compatible async LLM client.

    Works with providers that support chat.completions.create.
    """

    def __init__(self, config: CodePilotConfig):
        self.config = config
        self.enabled = bool(config.api_key and config.base_url)

        if not self.enabled:
            self.client = None
            return

        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError:
            self.enabled = False
            self.client = None
            return

        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.2,
    ) -> dict:
        """
        Call chat completions and return the assistant message dict.
        """
        if not self.enabled or self.client is None:
            raise LLMError(
                "Missing CODEPILOT_API_KEY or OpenAI SDK. Please create a .env file and install openai."
            )

        kwargs: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = tools

        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}") from e

        try:
            return response.choices[0].message.model_dump(
                exclude_none=True,
                mode="json",
            )
        except (AttributeError, IndexError) as e:
            raise LLMError(f"Unexpected LLM response format: {response}") from e

    async def chat_text(
        self,
        messages: list[dict],
        temperature: float = 0.2,
    ) -> str:
        """
        Compatibility helper for simple text-only calls.
        """
        message = await self.chat_completion(
            messages=messages,
            temperature=temperature,
        )
        return message.get("content") or ""


async def chat_completion_async(
    messages: list[dict],
    config: CodePilotConfig,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    temperature: float = 0.2,
) -> dict:
    client = LLMClient(config)
    return await client.chat_completion(
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )


def chat_completion(
    messages: list[dict],
    config: CodePilotConfig,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    temperature: float = 0.2,
) -> dict:
    """
    Synchronous wrapper for the async OpenAI-compatible client.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            chat_completion_async(
                messages=messages,
                config=config,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
            )
        )

    raise LLMError("chat_completion cannot be called synchronously inside a running event loop.")


def chat_text(
    messages: list[dict],
    config: CodePilotConfig,
    temperature: float = 0.2,
) -> str:
    """
    Compatibility helper for simple text-only calls.
    """
    message = chat_completion(
        messages=messages,
        config=config,
        temperature=temperature,
    )
    return message.get("content") or ""
