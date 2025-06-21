import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

from app.chatbot.chatbot_models import AgentMessage, StreamChunk
from app.common.models import StreamStep
from app.common.workflows import BaseAgentWorkflow
from app.common.models import Role


class KrishnaMiniWorkflow(BaseAgentWorkflow):
    """Fast response workflow with minimal processing steps."""

    async def run(self) -> AsyncGenerator[StreamChunk, None]:
        """Run the fast workflow."""

        async def drive_workflow() -> None:
            """Drive the workflow."""
            await self._generate_response()
            await self.state.stream_queue.put(None)

        task = asyncio.create_task(drive_workflow())
        while True:
            chunk = await self.state.stream_queue.get()
            if chunk is None:
                break
            yield chunk
        await task

    async def _generate_response(self) -> None:
        """Generate a direct response without multi-step reasoning."""
        conversation_history = self._build_conversation_history()

        prompt = f"""
        {conversation_history}
        
        [Current Query]
        {self.state.user_message}
        
        Provide a clear, helpful response to the user's question.
        Use markdown formatting for better readability.
        Be concise but comprehensive.
        """

        await self.state.stream_queue.put(StreamChunk(content="", step=StreamStep.FINAL_RESPONSE, step_title="Quick Answer"))

        response_content = ""
        async for chunk in self.chatbot.stream_response(prompt):
            response_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.FINAL_RESPONSE, step_title=None))
            await asyncio.sleep(0.01)

        self.state.agent_message = response_content
        self.state.messages.append(AgentMessage(message=self.state.agent_message, role=Role.ASSISTANT, timestamp=datetime.now(timezone.utc)))
