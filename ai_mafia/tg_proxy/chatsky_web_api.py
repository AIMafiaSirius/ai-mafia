import asyncio
import os

import requests
import telegram as tg
from chatsky import Message
from chatsky.messengers.common.interface import CallbackMessengerInterface
from dotenv import load_dotenv
from fastapi import FastAPI

from ai_mafia.config import load_config

load_dotenv()

config = load_config().chatsky

interface = CallbackMessengerInterface()

app = FastAPI()

bot = tg.Bot(os.environ["TG_TOKEN"])


@app.post("/chat", response_model=Message)
async def respond(
    user_message: Message,
):
    upd = tg.Update.de_json(user_message.original_message)
    user_message.original_message = upd
    context = await interface.on_request_async(user_message, upd.effective_user.id)
    return context.last_response


async def send_message(ctx_id: str, chat_id: int):
    await asyncio.sleep(3)
    context = await interface.on_request_async(Message(text="_ready_"), ctx_id)
    await bot.send_message(chat_id=chat_id, text=context.last_response.text)


def send_room_is_ready_signal(ctx_id: str, chat_id: int):
    asyncio.create_task(send_message(ctx_id, chat_id))  # noqa: RUF006


@app.post("/skip", response_model=Message)
async def skip(
    ctx_id: str,
):
    msg = Message(text="_skip_")
    context = await interface.on_request_async(msg, ctx_id)
    return context.last_response


def send_skip_signal(ctx_id: str):
    requests.post(config.make_endpoint("skip"), params={"ctx_id": ctx_id}, timeout=5)
