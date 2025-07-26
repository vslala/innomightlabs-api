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
    ):
        stage = os.getenv("STAGE", "local").lower()
        if BedrockEmbeddings is None:
            raise ImportError("langchain-aws is not installed; pip install langchain-aws")

        # Only use profile for local development
        if stage == "local":
            self.model = BedrockEmbeddings(model_id=model_id, region_name=region_name, credentials_profile_name=os.getenv("AWS_PROFILE", "searchexpert"))
        else:
            self.model = BedrockEmbeddings(
                model_id=model_id,
                region_name=region_name,
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple documents/texts at once.
        """
        return self.model.embed_documents(texts)

    def embed_single_text(self, text: str) -> list[float]:
        """
        Embed a single query/text.
        """
        return self.model.embed_query(text)
