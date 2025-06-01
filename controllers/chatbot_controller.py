from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from components.chatbot import BaseChatbot, ChatbotFactory
from models.agentic_workflow_models import StreamStep
from models.requests import UserRequest
from workflows.chat_agent_workflow import AgentState, AgenticWorkflow


prefix = "/api/v1/chatbot"
router = APIRouter(prefix=prefix)


@router.post("/ask")
async def ask_chatbot(
    request: UserRequest,
    chatbot: BaseChatbot = Depends(lambda: ChatbotFactory.create_chatbot("google", "gemini-2.0-flash")),
) -> StreamingResponse:
    """
    Endpoint to ask the chatbot a question.
    This endpoint initializes the agentic workflow and processes the user's request.

    Args:
        request (UserRequest): _description_
    """
    state = AgentState(
        messages=[request.message],
        user_message=request.message,
        agent_message="",
        scratchpad="",
        stream_queue=None,
    )
    agentic_workflow = AgenticWorkflow(state=state, chatbot=chatbot)

    async def response_streamer():
        async for chunk in agentic_workflow.run():
            if chunk["step"] == StreamStep.THIKING:
                print(f"Thinking.... {chunk['content']}")
            else:
                yield f"data: {chunk['content']}\n\n"

    return StreamingResponse(response_streamer(), media_type="text/event-stream")
