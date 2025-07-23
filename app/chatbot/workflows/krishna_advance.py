import asyncio
from typing import AsyncGenerator
from loguru import logger

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState, StreamChunk
from langgraph.graph import StateGraph, START, END

from app.chatbot.workflows.helpers.krishna_advance_helpers import KrishnaAdvanceWorkflowHelper, route_condition
from app.common.workflows import BaseAgentWorkflow


class KrishnaAdvanceWorkflow(BaseAgentWorkflow):
    """
    Workflow for Krishna, an advanced agent.
    This workflow is designed to handle complex tasks and interactions.
    """

    def __init__(self, state: AgentState, chatbot: BaseChatbot):
        super().__init__(state, chatbot)
        self.conversation_history = self._build_conversation_history()  # cache history for lifecycle of the workflow

    async def run(self) -> AsyncGenerator[StreamChunk, None]:
        """
        Run the Krishna workflow and yield stream chunks.
        This method implements the specific logic for Krishna's advanced tasks.
        """
        helper = KrishnaAdvanceWorkflowHelper(self.chatbot)
        graph = StateGraph(AgentState)
        graph.add_node("prompt_builder", helper.prompt_builder)
        graph.add_node("thinker", helper.thinker)
        graph.add_node("response_validator", helper.validate_response)
        graph.add_node("router", helper.router)

        graph.add_edge(START, "prompt_builder")
        graph.add_edge("prompt_builder", "thinker")
        graph.add_edge("thinker", "response_validator")
        graph.add_conditional_edges("response_validator", route_condition, {"final_response": END, "router": "router", "thinker": "thinker"}, END)
        graph.add_conditional_edges("router", route_condition, {"final_response": END, "router": "prompt_builder", "thinker": "thinker"}, END)

        app = graph.compile()

        try:

            async def drive_workflow() -> None:
                try:
                    state = self.state
                    async for _ in app.astream(state):
                        pass
                finally:
                    await self.state.stream_queue.put(None)

            task = asyncio.create_task(drive_workflow())
            while True:
                chunk = await self.state.stream_queue.get()
                if chunk is None:
                    break
                yield chunk
            await task
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            await self.state.stream_queue.put(None)
            raise e
