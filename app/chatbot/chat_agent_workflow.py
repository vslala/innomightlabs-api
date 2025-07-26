import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from langgraph.graph import StateGraph, START, END

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentMessage, AgentState, StreamChunk, StreamStep
from app.common.models import Role


class AgenticWorkflow:
    """Base class for agentic workflows."""

    def __init__(
        self,
        state: AgentState,
        chatbot: BaseChatbot,
    ):
        self.state = state
        self.chatbot = chatbot

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
            await self.state.stream_queue.put(None)  # Signal the end of the stream

        task = asyncio.create_task(drive_workflow())
        while True:
            chunk = await self.state.stream_queue.get()
            if chunk is None:
                break
            yield chunk

        await task

    def _build_conversation_history(self) -> str:
        """Build the conversation history from the state."""
        return "\n".join(msg.get_formatted_prompt() for msg in self.state.messages)

    async def _analyze_query(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Analyze and understand the user's query."""
        conversation_history = "\n".join(msg.get_formatted_prompt() for msg in state.messages)

        analysis_prompt = f"""
        Analyze the following user query and conversation context:
        
        [Conversation History]
        {conversation_history}
        
        [Current Query]
        \"\"\"
        {state.user_message}
        \"\"\"
        
        Provide a brief analysis of:
        1. What the user is asking for
        2. Key requirements or constraints
        3. Any ambiguities that need clarification
        
        Keep this concise (2-3 sentences max).
        """

        analysis_content = ""
        await self.state.stream_queue.put(StreamChunk(content="🔍 Analyzing your query...", step=StreamStep.ANALYSIS, step_title="Query Analysis"))

        async for chunk in self.chatbot.stream_response(analysis_prompt):
            analysis_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.ANALYSIS, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.analysis = analysis_content

    async def _plan_approach(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Plan the approach to solve the user's query."""
        planning_prompt = f"""
        Based on this analysis:
        {state.analysis}
        
        Create a step-by-step plan to address the user's query: "{state.user_message}"
        
        Provide a numbered list of 3-5 concrete steps you'll take to provide a comprehensive answer.
        Keep each step brief (one line each).
        """

        plan_content = ""
        await self.state.stream_queue.put(StreamChunk(content="📋 Planning approach...", step=StreamStep.PLANNING, step_title="Solution Planning"))

        async for chunk in self.chatbot.stream_response(planning_prompt):
            plan_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.PLANNING, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.thought = plan_content

    async def _execute_reasoning(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Execute the reasoning process step by step."""
        reasoning_prompt = f"""
        Analysis: {state.analysis}
        
        Plan: {state.thought}
        
        Now execute this plan step by step to answer: "{state.user_message}"
        
        Work through each step of your plan, providing detailed reasoning and insights.
        Think deeply about each aspect and show your work.
        """

        reasoning_content = ""
        await self.state.stream_queue.put(StreamChunk(content="🧠 Executing reasoning...", step=StreamStep.REASONING, step_title="Deep Reasoning"))

        async for chunk in self.chatbot.stream_response(reasoning_prompt):
            reasoning_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.REASONING, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.reasoning = reasoning_content

    async def _synthesize_insights(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Synthesize insights from the reasoning process."""
        synthesis_prompt = f"""
        Based on the reasoning above:
        {state.reasoning}
        
        Synthesize the key insights and conclusions. What are the most important takeaways?
        Identify any patterns, implications, or recommendations that emerge.
        
        Keep this focused and actionable (3-4 key points max).
        """

        synthesis_content = ""
        await self.state.stream_queue.put(StreamChunk(content="💡 Synthesizing insights...", step=StreamStep.SYNTHESIS, step_title="Key Insights"))

        async for chunk in self.chatbot.stream_response(synthesis_prompt):
            synthesis_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.SYNTHESIS, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.synthesis = synthesis_content

    async def _draft_response(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Create initial draft response."""
        draft_prompt = f"""
        Based on the complete reasoning process:
        
        Analysis: {state.analysis}
        Plan: {state.thought}
        Reasoning: {state.reasoning}
        Insights: {state.synthesis}
        
        Create a comprehensive draft answer to: "{state.user_message}"
        
        Write your response using markdown formatting (headings, bullet points, code snippets where relevant).
        Do NOT wrap your response in code blocks or markdown fences.
        Provide a clear, well-structured answer that directly addresses the user's question.
        """

        draft_content = ""
        await self.state.stream_queue.put(StreamChunk(content="📝 Drafting response...", step=StreamStep.DRAFT, step_title="Initial Draft"))

        async for chunk in self.chatbot.stream_response(draft_prompt):
            draft_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.DRAFT, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.draft_response = draft_content

    async def _evaluate_quality(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Evaluate the quality of the draft response."""
        evaluation_prompt = f"""
        
        Evaluate this draft response for the query: "{state.user_message}"
        
        DRAFT RESPONSE:
        {state.draft_response}
        
        Rate the response on a scale of 1-10 and provide specific feedback:
        
        1. **Accuracy**: Are the facts and information correct?
        2. **Completeness**: Does it fully address the user's question?
        3. **Clarity**: Is it easy to understand and well-structured?
        4. **Actionability**: Can the user act on this advice?
        5. **Relevance**: Does it stay focused on the user's needs?
        
        Format your response as:
        OVERALL_SCORE: [1-10]
        FEEDBACK: [Specific areas for improvement]
        DECISION: [APPROVE/REFINE]
        
        Only APPROVE if score is 8+ and no critical issues exist.
        """

        evaluation_content = ""
        await self.state.stream_queue.put(StreamChunk(content="🔍 Evaluating quality...", step=StreamStep.EVALUATION, step_title="Quality Check"))

        async for chunk in self.chatbot.stream_response(evaluation_prompt):
            evaluation_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.EVALUATION, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.evaluation = evaluation_content

        # Parse decision
        if "DECISION: APPROVE" in evaluation_content:
            state.needs_refinement = False
        else:
            state.needs_refinement = True
            state.refinement_count = getattr(state, "refinement_count", 0) + 1

    async def _refine_response(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Refine the response based on evaluation feedback."""
        refinement_prompt = f"""
        [Conversation History]
        {self._build_conversation_history()}
        
        [Current User Message]
        "{state.user_message}"
        
        CURRENT DRAFT:
        {state.draft_response}
        
        EVALUATION FEEDBACK:
        {state.evaluation}
        
        Based on the feedback, create an improved version that addresses all the identified issues.
        Focus on the specific areas mentioned in the feedback while maintaining the overall structure.
        
        Make it more accurate, complete, clear, and actionable.
        Use markdown formatting but do NOT wrap your response in code blocks or markdown fences.
        Provide the refined content directly.
        """

        refined_content = ""
        await self.state.stream_queue.put(
            StreamChunk(
                content=f"🔄 Refining response (attempt {state.refinement_count})...",
                step=StreamStep.REFINEMENT,
                step_title=f"Refinement #{state.refinement_count}",
            )
        )

        async for chunk in self.chatbot.stream_response(refinement_prompt):
            refined_content += str(chunk)
            await self.state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.REFINEMENT, step_title=None))
            yield state
            await asyncio.sleep(0.1)

        state.draft_response = refined_content

    def _should_continue_refinement(self, state: AgentState) -> bool:
        """Determine if refinement should continue."""
        max_refinements = 3  # Prevent infinite loops
        return state.needs_refinement and getattr(state, "refinement_count", 0) < max_refinements

    async def _finalize_answer(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Finalize the approved response."""
        # Send status message first
        await self.state.stream_queue.put(StreamChunk(content="", step=StreamStep.FINAL_RESPONSE, step_title="Final Answer"))

        # Use the refined/approved draft as final response
        state.agent_message = state.draft_response

        # Stream the final response preserving line breaks and formatting
        lines = state.draft_response.split("\n")
        for line in lines:
            if line.strip():  # Only send non-empty lines
                await self.state.stream_queue.put(StreamChunk(content=line + "\n", step=StreamStep.FINAL_RESPONSE, step_title=None))
            else:
                await self.state.stream_queue.put(StreamChunk(content="\n", step=StreamStep.FINAL_RESPONSE, step_title=None))
            yield state
            await asyncio.sleep(0.02)

        state.messages.append(AgentMessage(message=state.agent_message, role=Role.ASSISTANT, timestamp=datetime.now(timezone.utc)))

    def _build_graph(self):
        """Build the state graph with quality assurance loop."""
        graph = StateGraph(AgentState)

        # Add all nodes (using unique names to avoid state field conflicts)
        graph.add_node("query_analysis", self._analyze_query)
        graph.add_node("approach_planning", self._plan_approach)
        graph.add_node("deep_reasoning", self._execute_reasoning)
        graph.add_node("insight_synthesis", self._synthesize_insights)
        graph.add_node("response_drafting", self._draft_response)
        graph.add_node("quality_evaluation", self._evaluate_quality)
        graph.add_node("response_refinement", self._refine_response)
        graph.add_node("answer_finalization", self._finalize_answer)

        # Main reasoning pipeline
        graph.add_edge(START, "query_analysis")
        graph.add_edge("query_analysis", "approach_planning")
        graph.add_edge("approach_planning", "deep_reasoning")
        graph.add_edge("deep_reasoning", "insight_synthesis")
        graph.add_edge("insight_synthesis", "response_drafting")
        graph.add_edge("response_drafting", "quality_evaluation")

        # Quality assurance loop
        graph.add_conditional_edges("quality_evaluation", self._should_continue_refinement, {True: "response_refinement", False: "answer_finalization"})
        graph.add_edge("response_refinement", "quality_evaluation")
        graph.add_edge("answer_finalization", END)

        return graph
