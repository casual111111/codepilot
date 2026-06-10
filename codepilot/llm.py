from codepilot.config import CodePilotConfig


class LLMError(Exception):
    pass


class LLMClient:
    """
    OpenAI-compatible synchronous LLM client.
    """

    def __init__(self, config: CodePilotConfig):
        self.config = config
        self.enabled = bool(config.api_key and config.base_url)

        if not self.enabled:
            self.client = None
            return

        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            self.enabled = False
            self.client = None
            return

        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def close(self) -> None:
        if self.client is None:
            return

        close = getattr(self.client, "close", None)

        if close is not None:
            close()

    def chat_completion(
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
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}") from e

        try:
            return response.choices[0].message.model_dump(
                exclude_none=True,
                mode="json",
            )
        except (AttributeError, IndexError) as e:
            raise LLMError(f"Unexpected LLM response format: {response}") from e

    def chat_text(
        self,
        messages: list[dict],
        temperature: float = 0.2,
    ) -> str:
        """
        Compatibility helper for simple text-only calls.
        """
        message = self.chat_completion(
            messages=messages,
            temperature=temperature,
        )
        return message.get("content") or ""


def chat_completion(
    messages: list[dict],
    config: CodePilotConfig,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    temperature: float = 0.2,
) -> dict:
    """
    Synchronous wrapper for the OpenAI-compatible client.
    """
    client = LLMClient(config)

    try:
        return client.chat_completion(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )
    finally:
        client.close()


async def chat_completion_async(
    messages: list[dict],
    config: CodePilotConfig,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    temperature: float = 0.2,
) -> dict:
    """
    Async-compatible wrapper for callers that still import this name.
    """
    return chat_completion(
        messages=messages,
        config=config,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )


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
