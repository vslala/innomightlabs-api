from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.common.middlewares import UserPopulationMiddleware
from app.common import get_controllers

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
