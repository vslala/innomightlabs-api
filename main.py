from fastapi import FastAPI
from controllers import chatbot_controller

app = FastAPI()

app.include_router(router=chatbot_controller.router, tags=["chatbot"])
