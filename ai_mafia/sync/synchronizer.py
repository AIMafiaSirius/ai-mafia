import requests
from bson.objectid import ObjectId
from fastapi import FastAPI

from ai_mafia.config import load_config
from ai_mafia.db.routines import mark_user_as_ready

from .polling import start_polling

app = FastAPI()

config = load_config().sync


@app.post("/user_is_ready")
async def user_is_ready(user_db_id: str, room_db_id: str, ctx_id: str) -> None:
    mark_user_as_ready(user_db_id=ObjectId(user_db_id), room_db_id=ObjectId(room_db_id))
    await start_polling(ObjectId(room_db_id), ctx_id, interval=1)


def send_ready_signal(user_db_id: ObjectId, room_db_id: ObjectId, ctx_id):
    requests.post(
        url=config.make_endpoint("user_is_ready"),
        params={
            "user_db_id": str(user_db_id),
            "room_db_id": str(room_db_id),
            "ctx_id": str(ctx_id),
        },
        timeout=5,
    )
