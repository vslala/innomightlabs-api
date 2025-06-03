from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.workflows import chatbot_controller
from app.common.config import ALL_CONTROLLERS

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

for controller in ALL_CONTROLLERS:
    app.include_router(controller().router)
    