from typing import AsyncGenerator

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.chatbot import BaseChatbot
from app.chatbot.chat_agent_workflow import AgenticWorkflow
from app.chatbot.chatbot_models import AgentMessage, AgentMessageSummary, AgentRequest, AgentState, AgentStreamResponse


class ChatbotService:
    def __init__(self, chatbot: BaseChatbot, embedding_model: GoogleGenerativeAIEmbeddings) -> None:
        self.chatbot = chatbot
        self.embedding_model = embedding_model

    """
    Service class for handling chatbot-related operations.
    This class contains methods for interacting with the chatbot.
    """

    async def ask_async(self, request: AgentRequest) -> AsyncGenerator[AgentStreamResponse, None]:
        """Send a message to the chatbot and return the response."""
        state = AgentState(
            messages=request.message_history,
            user_message=request.message,
        )
        workflow = AgenticWorkflow(
            state=state,
            chatbot=self.chatbot,
        )
        async for chunk in workflow.run():
            yield AgentStreamResponse(content=chunk["content"], step=chunk["step"], timestamp=request.timestamp)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding for the given text."""
        from asyncio import to_thread

        return await to_thread(self.embedding_model.embed_query, text, output_dimensionality=1536)

    async def summarize_with_title(self, past_summary: str, user_message: AgentMessage, agent_response: AgentMessage) -> AgentMessageSummary:
        message_exchange = "".join([user_message.get_formatted_prompt(), "\n", agent_response.get_formatted_prompt()])
        prompt = f"""
[System]
You are a JSON-only assistant. When asked, you will output exactly one JSON object and nothing else—no markdown fences, no explanations, no extra keys.

Here is the JSON Schema you must follow exactly (no deviations):

```json
{{
  "type": "object",
  "properties": {{
    "title":   {{ "type": "string", "description": "A concise title for the conversation" }},
    "summary": {{ "type": "string", "description": "A brief summary of the main points and themes" }}
  }},
  "required": ["title", "summary"],
  "additionalProperties": false
}}

Understand it. And only provide json object for user's query.

[User]
Summarize the following message exchange and past summary of the user and the assistant.

[Past Conversation Summary]
{past_summary}

[Message Exchange]
{message_exchange}
        """
        llm_response = self.chatbot.get_text_response(prompt=prompt)
        output = AgentMessageSummary(title=f"{user_message.message}", summary=llm_response)
        return output
