import uvicorn
from fastapi import FastAPI

from ai_mafia.config import load_config
from ai_mafia.sync import synchronizer_app

app = FastAPI()

config = load_config().sync

if __name__ == "__main__":
    uvicorn.run(synchronizer_app, host=config.host, port=config.port)
