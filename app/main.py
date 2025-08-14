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

# Use FastAPI's built-in origin pattern matching for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?",
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
    try:
        from alembic.config import Config
        from alembic import command
        import io
        import sys

        # Capture output
        output = io.StringIO()

        # Create alembic config with absolute path
        import os

        config_path = os.path.join(os.getcwd(), "alembic.ini")
        alembic_cfg = Config(config_path)

        # Redirect stdout to capture output
        old_stdout = sys.stdout
        sys.stdout = output

        try:
            command.upgrade(alembic_cfg, "head")
            result = output.getvalue()
            return {"status": "success", "output": result}
        finally:
            sys.stdout = old_stdout

    except Exception as e:
        return {"status": "error", "output": str(e)}


asgi_handler = Mangum(app)


def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Lambda handler function"""
    logger.info("Lambda handler invoked", event=event, context=context)
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
