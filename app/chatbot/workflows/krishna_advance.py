import asyncio
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
        self.conversation_history = self._build_conversation_history()  # cache history for lifecycle of the workflow

    async def run(self) -> AsyncGenerator[StreamChunk, None]:
        """
        Run the Krishna workflow and yield stream chunks.
        """
        helper = KrishnaAdvanceWorkflowHelper(self.chatbot)
        graph = StateGraph(AgentState)

        # 1) prompt_builder: ask LLM to think or finish
        graph.add_node("prompt_builder", helper.prompt_builder)
        graph.add_node("thinker", helper.thinker)
        graph.add_node("validate_response", helper.validate_response)
        # 2) router: only if LLM asked for a tool
        graph.add_node("router", helper.router)
        # 3) final_response: emit the answer
        graph.add_node("final_response", helper.final_response)

        # Start → prompt_builder
        graph.add_edge(START, "prompt_builder")
        graph.add_edge("prompt_builder", "thinker")
        graph.add_edge("thinker", "validate_response")
        graph.add_conditional_edges("validate_response", lambda state: state.phase, {Phase.NEED_TOOL: "router", Phase.NEED_FINAL: "final_response"}, END)

        # After running the tool, always go back into prompt_builder
        graph.add_edge("router", "prompt_builder")

        # final_response → END
        graph.add_edge("final_response", END)

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
