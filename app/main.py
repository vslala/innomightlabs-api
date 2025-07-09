from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from mangum.types import LambdaContext
from app.common import get_controllers
from app.common.middlewares import UserPopulationMiddleware
from loguru import logger

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(UserPopulationMiddleware)

for controller in get_controllers():
    app.include_router(controller().router)


@app.post("/migrate")
async def run_migrations():
    """Run database migrations"""
    import subprocess

    try:
        result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True, check=True)
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "output": e.stderr}


asgi_handler = Mangum(app)


def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Lambda handler function"""
    headers = event.get("headers", {})
    user_agent = headers.get("User-Agent", headers.get("user-agent", ""))

    logger_context = {
        "request_id": context.aws_request_id,
        "user_agent": user_agent,
        "x-forwarded-for": headers.get("X-Forwarded-For", ""),
        "httpMethod": event.get("httpMethod", ""),
        "path": event.get("path", ""),
    }

    with logger.contextualize(**logger_context):
        logger.info("Request received", event=event, context=context)
        response = asgi_handler(event, context)
        logger.info("Response generated", response=response)
        return response
