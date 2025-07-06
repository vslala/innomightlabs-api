from abc import ABC, abstractmethod
import boto3
import os
from typing import Any, AsyncGenerator, Union
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_aws import ChatBedrock

region = "us-east-1"
bedrock_client = boto3.client("bedrock-runtime", region_name=region)


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
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)

    async def get_text_response_async(self, prompt: str) -> Union[str, list[Union[str, dict[Any, Any]]]]:
        response = await self.llm.ainvoke(prompt)
        return response.content

    async def stream_response(self, prompt: str) -> AsyncGenerator[Union[str, list[Union[str, dict[Any, Any]]]], None]:
        stream_response = self.llm.astream(prompt)
        async for chunk in stream_response:
            yield chunk.content


class ClaudeSonnetChatbot(BaseChatbot):
    def __init__(self, temperature: float = 0):
        self.llm = ChatBedrock(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            model_kwargs={"temperature": temperature},
            credentials_profile_name=os.getenv("AWS_PROFILE", "searchexpert"),
            region=os.getenv("AWS_REGION", "us-east-1"),
        )

    def get_text_response(self, prompt: str) -> str:
        response = self.llm.invoke(prompt)
        return response.text()

    async def get_text_response_async(self, prompt: str) -> Union[str, list[Union[str, dict[Any, Any]]]]:
        response = await self.llm.ainvoke(prompt)
        return response.content

    async def stream_response(self, prompt: str) -> AsyncGenerator[Union[str, list[Union[str, dict[Any, Any]]]], None]:
        async for chunk in self.llm.astream(prompt):
            yield chunk.content
