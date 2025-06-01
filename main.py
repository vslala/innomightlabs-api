from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controllers import chatbot_controller

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

app.include_router(router=chatbot_controller.router, tags=["chatbot"])
