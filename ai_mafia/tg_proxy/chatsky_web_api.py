import asyncio
import os

import telegram as tg
from chatsky import Message
from chatsky.messengers.common.interface import CallbackMessengerInterface
from dotenv import load_dotenv
from fastapi import FastAPI

from ai_mafia.config import load_config
from ai_mafia.db.models import RoomModel

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


async def send_message(ctx_id: str, chat_id: int, msg: str, time_sleep=5):
    await asyncio.sleep(time_sleep)
    context = await interface.on_request_async(Message(text=msg), ctx_id)
    await bot.send_message(chat_id=chat_id, text=context.last_response.text)


def send_signal(room: RoomModel | None, msg: str = "_skip_", timer=5):
    if room is None:
        msg = "Room not found :("
        raise ValueError(msg)
    coroutines = [send_message(player.ctx_id, player.chat_id, msg, timer) for player in room.list_players]
    [asyncio.create_task(coro) for coro in coroutines]


def send_message_to_others(room: RoomModel, user_id: str, msg: str):
    """Send message from specific user to other players in room"""
    coroutines = []
    for player in room.list_players:
        if player.user_id != user_id:
            coroutines.append(send_message(player.ctx_id, player.chat_id, msg, 0))  # noqa: PERF401
    [asyncio.create_task(coro) for coro in coroutines]
