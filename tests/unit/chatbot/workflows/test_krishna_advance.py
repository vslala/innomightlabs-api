from uuid import UUID
import pytest


@pytest.mark.skip(reason="This test is a dry run not an actual test")
@pytest.mark.asyncio
async def test_krishna_advance_workflow():
    """
    Test the KrishnaAdvanceWorkflow with a real chatbot and agent state.
    """
    from app.chatbot.chatbot_models import AgentState
    import app.chatbot.workflows.krishna_advance as krishna_advance
    from app.chatbot import ClaudeSonnetChatbot
    from app.user import User
    from app.common.config import RepositoryFactory

    state = AgentState(
        user=User(id=UUID("436078b3-bd17-4734-9682-14678ab9e0bc"), username="vslala"),
        conversation_id=UUID("320970b4-c785-4063-9333-33a99b130217"),
        user_message="""
Write me a python script that can multiply two numbers, e.g. 72737 and -12319.
""",
    )

    # Initialize the workflow with a real chatbot and repositories
    wf = krishna_advance.KrishnaAdvanceWorkflow(
        state=state,
        chatbot=ClaudeSonnetChatbot(),
        conversation_repository=RepositoryFactory.get_conversation_repository(),
        message_repository=RepositoryFactory.get_message_repository(),
    )

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
