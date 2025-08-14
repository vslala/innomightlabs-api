from abc import abstractmethod
import os

from langchain_aws import BedrockEmbeddings


class BaseVectorEmbedder:
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Must be implemented by child class")

    @abstractmethod
    def embed_single_text(self, text: str) -> list[float]:
        raise NotImplementedError("Must be implemented by child class")


class LangChainTitanEmbedder(BaseVectorEmbedder):
    """
    Embedding model that wraps LangChain’s BedrockEmbeddings integration.
    """

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v1",
        region_name: str = "us-east-1",
        max_tokens: int = 32000,
    ):
        stage = os.getenv("STAGE", "local").lower()
        if BedrockEmbeddings is None:
            raise ImportError("langchain-aws is not installed; pip install langchain-aws")

        # Model kwargs - keep minimal to avoid schema violations
        model_kwargs = {}

        # Only use profile for local development
        if stage == "local":
            self.model = BedrockEmbeddings(model_id=model_id, region_name=region_name, credentials_profile_name=os.getenv("AWS_PROFILE", "searchexpert"), model_kwargs=model_kwargs)
        else:
            self.model = BedrockEmbeddings(model_id=model_id, region_name=region_name, model_kwargs=model_kwargs)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple documents/texts at once.
        Truncates texts if they're too long to avoid token limit errors.
        """
        # Rough estimate: 1 token ≈ 4 characters for English text
        # Keep it well under 8192 tokens (≈ 32,000 characters)
        max_chars = 30000
        truncated_texts = [text[:max_chars] if len(text) > max_chars else text for text in texts]

        return self.model.embed_documents(truncated_texts)

    def embed_single_text(self, text: str) -> list[float]:
        """
        Embed a single query/text.
        Truncates text if it's too long to avoid token limit errors.
        """
        # Rough estimate: 1 token ≈ 4 characters for English text
        # Keep it well under 8192 tokens (≈ 32,000 characters)
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars]

        return self.model.embed_query(text)
