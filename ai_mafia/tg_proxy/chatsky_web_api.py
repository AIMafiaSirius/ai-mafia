import requests
import telegram as tg
from chatsky import Message
from chatsky.messengers.common.interface import CallbackMessengerInterface
from fastapi import FastAPI

from ai_mafia.config import load_config

config = load_config().chatsky

interface = CallbackMessengerInterface()

app = FastAPI()


@app.post("/chat", response_model=Message)
async def respond(
    user_message: Message,
):
    upd = tg.Update.de_json(user_message.original_message)
    user_message.original_message = upd
    context = await interface.on_request_async(user_message, upd.effective_user.id)
    return context.last_response


@app.post("/room_is_ready", response_model=Message)
async def room_is_ready(
    ctx_id: str,
):
    msg = Message(text="_ready_")
    context = await interface.on_request_async(msg, ctx_id)
    return context.last_response


def send_room_is_ready_signal(ctx_id: str):
    requests.post(config.make_endpoint("room_is_ready"), params={"ctx_id": ctx_id}, timeout=5)



@app.post("/skip", response_model=Message)
async def skip(
    ctx_id: str,
):
    msg = Message(text="\n")
    context = await interface.on_request_async(msg, ctx_id)
    return context.last_response


def send_skip_signal(ctx_id: str):
    requests.post(config.make_endpoint("skip"), params={"ctx_id": ctx_id}, timeout=5)
