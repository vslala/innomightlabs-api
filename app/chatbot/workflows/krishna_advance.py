import asyncio
import os
import shutil
from typing import AsyncGenerator
from loguru import logger

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState, Phase, StreamChunk
from langgraph.graph import StateGraph, START, END

from app.chatbot.conversation.conversation_repositories import ConversationRepository
from app.chatbot.messages.message_repositories import MessageRepository
from app.common.vector_embedders import BaseVectorEmbedder
from app.common.workflows import BaseAgentWorkflow, BaseWorkflowHelper


class KrishnaAdvanceWorkflow(BaseAgentWorkflow):
    """
    Workflow for Krishna, an advanced agent.
    This workflow is designed to handle complex tasks and interactions.
    """

    def __init__(
        self,
        state: AgentState,
        chatbot: BaseChatbot,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        embedder: BaseVectorEmbedder,
        workflow_helper: BaseWorkflowHelper,
    ):
        super().__init__(state, chatbot, message_repository=message_repository, conversation_repository=conversation_repository, embedder=embedder)
        self.workflow_helper = workflow_helper

    def _router(self, state: AgentState) -> str:
        """
        Route the workflow based on the current state.
        """
        if state.phase == Phase.NEED_TOOL:
            return "prompt_builder"
        elif state.phase == Phase.NEED_FINAL:
            return "persist_message_exchange"
        else:
            return "error_handler"

    async def run(self) -> AsyncGenerator[StreamChunk, None]:
        """
        Run the Krishna workflow and yield stream chunks.
        """
        shutil.rmtree("/tmp/prompts", ignore_errors=True)
        os.makedirs("/tmp/prompts", exist_ok=True)

        helper = self.workflow_helper
        graph = StateGraph(AgentState)

        # 1) prompt_builder: ask LLM to think or finish
        graph.add_node("prompt_builder", helper.prompt_builder)
        graph.add_node("thinker", helper.thinker)
        graph.add_node("parse_actions", helper.parse_actions)
        graph.add_node("execute_actions", helper.execute_actions)
        graph.add_node("router", self._router)
        graph.add_node("persist_message_exchange", helper.persist_message_exchange)
        graph.add_node("error_handler", helper.error_handler)

        # Start → prompt_builder
        graph.add_edge(START, "prompt_builder")
        graph.add_edge("prompt_builder", "thinker")
        graph.add_edge("thinker", "parse_actions")
        graph.add_edge("parse_actions", "execute_actions")
        graph.add_conditional_edges(
            "execute_actions", self._router, {"prompt_builder": "prompt_builder", "error_handler": "error_handler", "persist_message_exchange": "persist_message_exchange"}, END
        )
        graph.add_edge("persist_message_exchange", END)

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
