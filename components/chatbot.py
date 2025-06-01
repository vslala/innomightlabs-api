from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Union
from langchain_google_genai import ChatGoogleGenerativeAI


class BaseChatbot(ABC):
    def __init__(self, model_name: str, temperature: float = 0):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)

    def get_text_response(self, prompt: str) -> str:
        response = self.llm.invoke(prompt)
        return response.text()

    @abstractmethod
    async def get_text_response_async(self, prompt: str) -> Union[str, list[Union[str, dict[Any, Any]]]]:
        pass

    @abstractmethod
    async def stream_response(self, prompt: str) -> AsyncGenerator[Union[str, list[Union[str, dict[Any, Any]]]], None]:
        if False:
            yield  # This is to ensure the method is abstract and must be implemented in subclasses.
        pass


class GeminiChatbot(BaseChatbot):
    def __init__(self, model_name: str = "gemini-2.0-flash", temperature: float = 0):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature, streaming=True)

    async def get_text_response_async(self, prompt: str) -> Union[str, list[Union[str, dict[Any, Any]]]]:
        response = await self.llm.ainvoke(prompt)
        return response.content

    async def stream_response(self, prompt: str) -> AsyncGenerator[Union[str, list[Union[str, dict[Any, Any]]]], None]:
        stream_response = self.llm.astream(prompt)
        async for chunk in stream_response:
            yield chunk.content


class ChatbotFactory:
    @staticmethod
    def create_chatbot(owner: str, model_name: str, temperature: float = 0.0) -> BaseChatbot:
        return GeminiChatbot(model_name=model_name, temperature=temperature)
