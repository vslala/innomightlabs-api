from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from components.chatbot import BaseChatbot, ChatbotFactory
from models.agentic_workflow_models import StreamStep
from models.requests import UserRequest
from models.responses import AgentStreamResponse
from workflows.chat_agent_workflow import AgentState, AgenticWorkflow


prefix = "/api/v1/chatbot"
router = APIRouter(prefix=prefix)


@router.post(
    "/ask",
    response_class=StreamingResponse,
    response_model=None,
    responses={
        200: {
            "description": "Server‐Sent Events stream (text/event-stream)",
            "content": {"text/event-stream": {}},
        }
    },
)
async def ask_chatbot(
    request: UserRequest,
    chatbot: BaseChatbot = Depends(lambda: ChatbotFactory.create_chatbot("google", "gemini-2.0-flash")),
) -> StreamingResponse:
    """
    Endpoint to ask the chatbot a question.
    This endpoint initializes the agentic workflow and processes the user's request.
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
                response = AgentStreamResponse(content=chunk["content"], step=chunk["step"])
                yield f"data: {response.model_dump_json()}\n\n"
            else:
                response = AgentStreamResponse(content=chunk["content"], step=chunk["step"])
                yield f"data: {response.model_dump_json()}\n\n"

    return StreamingResponse(response_streamer(), media_type="text/event-stream")
