import asyncio
import os
import shutil
from typing import AsyncGenerator
from loguru import logger

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState, Phase, StreamChunk
from langgraph.graph import StateGraph, START, END

from app.chatbot.workflows.helpers.krishna_advance_helpers import KrishnaAdvanceWorkflowHelper
from app.common.workflows import BaseAgentWorkflow


class KrishnaAdvanceWorkflow(BaseAgentWorkflow):
    """
    Workflow for Krishna, an advanced agent.
    This workflow is designed to handle complex tasks and interactions.
    """

    def __init__(self, state: AgentState, chatbot: BaseChatbot):
        super().__init__(state, chatbot)
        # state.messages.append(AgentMessage(message=state.user_message, role=Role.USER))

    def _router(self, state: AgentState) -> str:
        """
        Route the workflow based on the current state.
        """
        if state.phase == Phase.NEED_TOOL:
            return "prompt_builder"
        elif state.phase == Phase.NEED_FINAL:
            return "__END__"
        else:
            return "error_handler"

    async def run(self) -> AsyncGenerator[StreamChunk, None]:
        """
        Run the Krishna workflow and yield stream chunks.
        """
        shutil.rmtree("/tmp/prompts", ignore_errors=True)
        os.makedirs("/tmp/prompts", exist_ok=True)

        helper = KrishnaAdvanceWorkflowHelper(self.chatbot)
        graph = StateGraph(AgentState)

        # 1) prompt_builder: ask LLM to think or finish
        graph.add_node("prompt_builder", helper.prompt_builder)
        graph.add_node("thinker", helper.thinker)
        graph.add_node("parse_actions", helper.parse_actions)
        graph.add_node("execute_actions", helper.execute_actions)
        graph.add_node("router", self._router)
        graph.add_node("error_handler", helper.final_response)

        # Start → prompt_builder
        graph.add_edge(START, "prompt_builder")
        graph.add_edge("prompt_builder", "thinker")
        graph.add_edge("thinker", "parse_actions")
        graph.add_edge("parse_actions", "execute_actions")
        graph.add_conditional_edges("execute_actions", self._router, {"prompt_builder": "prompt_builder", "error_handler": "error_handler", "__END__": END}, END)

        app = graph.compile()

        try:

            async def drive_workflow() -> None:
                try:
                    state = self.state
                    async for _ in app.astream(state, {"recursion_limit": 100}):
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
