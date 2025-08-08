from uuid import UUID
import pytest


@pytest.mark.skip(reason="This test is a dry run not an actual test")
@pytest.mark.asyncio
async def test_krishna_advance_workflow():
    """
    Test the KrishnaAdvanceWorkflow with a real chatbot and agent state.
    """
    from app.chatbot.chatbot_models import AgentState, AgentMessage, Role
    import app.chatbot.workflows.krishna_advance as krishna_advance
    from app.chatbot import ClaudeSonnetChatbot
    from app.user import User
    from datetime import datetime, timezone

    # Create a more realistic test scenario with conversation history
    messages = [
        AgentMessage(message="Hi, my friend John loves astronomy and reading science fiction books.", role=Role.USER, timestamp=datetime.now(timezone.utc)),
        AgentMessage(
            message="That's great! Astronomy and science fiction are fascinating interests.\
                        Is there anything specific about these topics that John particularly enjoys?",
            role=Role.ASSISTANT,
            timestamp=datetime.now(timezone.utc),
        ),
    ]

    state = AgentState(
        user=User(id=UUID("436078b3-bd17-4734-9682-14678ab9e0bc"), username="vslala"),
        messages=messages,
        # user_message="Now that I have told you about my friend, what should I gift him on his birthday?"
        # user_message="John wants to multiply two numbers e.g 72737 and -12319 using a python script"
        # user_message="Estimate π by counting the fraction of points that fall inside the quarter‑circle of radius 1 (i.e. x²+y²≤1).",
        user_message="""
Write me a python script that can multiply two numbers, e.g. 72737 and -12319.
""",
    )

    # Initialize the workflow with a real chatbot
    wf = krishna_advance.KrishnaAdvanceWorkflow(state=state, chatbot=ClaudeSonnetChatbot())

    print("Starting workflow execution...")

    # Collect chunks for analysis
    chunks = []

    async def run_workflow():
        async for chunk in wf.run():
            print(f"{chunk.content}", end="", flush=True)
            yield chunk.content

    async for chunk in run_workflow():
        chunks.append(chunk)

    print(f"\nWorkflow completed. Total chunks: {len(chunks)}")
