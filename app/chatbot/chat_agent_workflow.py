import asyncio
from typing import AsyncGenerator
from langgraph.graph import StateGraph, START, END

from app.workflows.chatbot import BaseChatbot
from app.workflows.models import AgentState, StreamChunk, StreamStep


class AgenticWorkflow:
    """Base class for agentic workflows."""

    def __init__(
        self,
        state: AgentState,
        chatbot: BaseChatbot,
    ):
        self.state = state
        self.chatbot = chatbot
        self.state["stream_queue"] = asyncio.Queue()

    async def run(self) -> AsyncGenerator[StreamChunk, None]:
        """Run the workflow."""
        graph = self._build_graph()
        app = graph.compile()

        async def drive_workflow() -> None:
            """Drive the workflow and yield states."""
            state = self.state
            async for wrapped_state in app.astream(state):
                # log for metrics and debugging
                # print(f"State: {wrapped_state}")
                pass
            await self.state["stream_queue"].put(None)  # Signal the end of the stream

        task = asyncio.create_task(drive_workflow())
        while True:
            chunk = await self.state["stream_queue"].get()
            if chunk is None:
                break
            yield chunk

        await task

    async def _chain_of_thoughts(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Process the user's message and generate a chain of thoughts to better understand and answer user's query."""
        chain_of_thoughts_prompt = f"""
        You are a thoughtful and analytical assistant. Your task is to answer the user's question in two steps:
        1. Chain of Thoughts: Think step by step, and write down your reasoning process as you try to understand what the user really wants, clarify the request if needed, and plan your answer.
        2. Final Answer: Based on your chain of thoughts, provide a clear and helpful answer.

        User's question:
        \"\"\"
        {state["user_message"]}
        \"\"\"

        Let's think step by step.
        """
        state["scratchpad"] = ""
        async for chunk in self.chatbot.stream_response(chain_of_thoughts_prompt):
            state["scratchpad"] += str(chunk)
            await self.state["stream_queue"].put(StreamChunk(content=str(chunk), step=StreamStep.THIKING))
            yield state
            await asyncio.sleep(0.5)

    async def _finalize_answer(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Finalize the answer based on the given chain of thoughts."""

        async for chunk in self.chatbot.stream_response(f"{state.get('scratchpad', '')}\n\n Based on the above chain of thoughts, please provide a clear and concise answer to the user's question in markdown format."):
            state["agent_message"] += str(chunk)
            await self.state["stream_queue"].put(StreamChunk(content=str(chunk), step=StreamStep.FINAL_RESPONSE))
            yield state
            await asyncio.sleep(0.5)
        state["messages"].append(state["agent_message"])

    def _build_graph(self):
        """Build the state graph for the agentic workflow."""
        graph = StateGraph(AgentState)
        graph.add_node("chain_of_thoughts", self._chain_of_thoughts)
        graph.add_node("finalize_answer", self._finalize_answer)

        graph.add_edge(START, "chain_of_thoughts")
        graph.add_edge("chain_of_thoughts", "finalize_answer")
        graph.add_edge("finalize_answer", END)
        return graph
