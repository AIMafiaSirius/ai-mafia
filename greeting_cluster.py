from typing import TYPE_CHECKING

import chatsky.conditions as cnd
import chatsky.destinations as dst
import telegram as tg
import uvicorn
from chatsky import (
    PRE_TRANSITION,
    RESPONSE,
    TRANSITIONS,
    BaseCondition,
    BaseProcessing,
    BaseResponse,
    Context,
    Message,
    MessageInitTypes,
    Pipeline,
)
from chatsky import Transition as Tr
from chatsky.messengers.common.interface import CallbackMessengerInterface
from dotenv import load_dotenv
from fastapi import FastAPI

from ai_mafia.config import load_config
from ai_mafia.db.routines import add_game_room, add_user, find_game_room, find_user, get_random_room

if TYPE_CHECKING:
    from ai_mafia.db.models import RoomModel, UserModel

load_dotenv()


class NewRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        name = str(ctx.last_request.text)
        room = add_game_room(name)
        return f"Данные по комнате:\
        \nId: {room.room_id}\
        \nНазвание: {name}\
        \nЧисло участников: {len(room.list_users)}/10"


class RandomRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room: RoomModel = ctx.misc["room"]
        return f"""Данные по комнате:
Id: {room.room_id}
Название: {room.name}
Число участников: {len(room.list_users)}/10

Присоединиться?"""


class RandomRoomExistCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room = get_random_room()
        if room is not None:
            ctx.misc["room"] = room
            return True
        return False


class RoomExistCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room = find_game_room(ctx.last_request.text)
        if room is not None:
            ctx.misc["room"] = room
            return True
        return False


class InitSessionProcessing(BaseProcessing):
    """
    Add user tg id to database.
    """

    async def call(self, ctx: Context):
        tg_info: tg.Update = ctx.last_request.original_message
        tg_id = tg_info.effective_user.id
        user_nickname = tg_info.effective_user.name
        user_info = find_user(tg_id)
        if user_info is None:
            user_info = add_user(tg_id, user_nickname)
        ctx.misc["user_info"] = user_info


class GreetingResponse(BaseResponse):
    """
    Greet and provide info about user
    """

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        return f"Привет, {user_info.tg_nickname}! Вам нужна инструкция по игре?"


greeting_script = {
    "global_flow": {
        "start_node": {},
        "fallback_node": {
            RESPONSE: "К сожалению я не могу обработать такую команду, введите другую",
            TRANSITIONS: [Tr(dst=dst.Previous())],
        },
    },
    "greeting_flow": {
        "start_node": {
            PRE_TRANSITION: {"init": InitSessionProcessing()},
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))],
        },
        "greeting_node": {
            RESPONSE: GreetingResponse(),
            TRANSITIONS: [
                Tr(dst=("instruction"), cnd=cnd.ExactMatch("Да")),
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Нет")),
            ],
        },
        "instruction": {
            RESPONSE: "...",
            TRANSITIONS: [Tr(dst=("to_room_flow", "choose"))],
        },
    },
    "to_room_flow": {
        "choose": {
            RESPONSE: "Создай комнату или присоединись к существующей",
            TRANSITIONS: [
                Tr(dst=("enter_id"), cnd=cnd.ExactMatch("Присоединиться")),
                Tr(dst=("make"), cnd=cnd.ExactMatch("Создать")),
            ],
        },
        "make": {
            RESPONSE: "Введите название для комнаты",
            TRANSITIONS: [Tr(dst=("new"))],
        },
        "new": {
            RESPONSE: NewRoomResponse(),
            TRANSITIONS: [
                Tr(dst=("choose"), cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
        "enter_id": {
            RESPONSE: "Введите ID комнаты или присоединитесь к случайной",
            TRANSITIONS: [
                Tr(dst=("random_id"), cnd=cnd.All(cnd.ExactMatch("К случайной"), RandomRoomExistCondition())),
                Tr(
                    dst=("random_not_found"),
                    cnd=cnd.All(cnd.ExactMatch("К случайной"), cnd.Not(RandomRoomExistCondition())),
                ),
                Tr(dst="join_id", cnd=cnd.All(cnd.Not(cnd.ExactMatch("К случайной")), RoomExistCondition())),
                Tr(
                    dst="room_not_found",
                    cnd=cnd.All(cnd.Not(cnd.ExactMatch("К случайной")), cnd.Not(RoomExistCondition())),
                ),
            ],
        },
        "random_not_found": {
            RESPONSE: "Нет открытых комнат. Создать новую?",
            TRANSITIONS: [
                Tr(dst="make", cnd=cnd.ExactMatch("Да")),
                Tr(dst="enter_id", cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "random_id": {
            RESPONSE: RandomRoomResponse(),
            TRANSITIONS: [
                Tr(dst="choose", cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
        "join_id": {RESPONSE: "вы присоединились к комнате"},
        "room_not_found": {RESPONSE: "комната с таким ID не найдена"},
    },
    "in_room_flow": {
        "not_ready": {
            RESPONSE: "Нажмите готов для подтверждения игры",
            TRANSITIONS: [
                Tr(dst=("ready"), cnd=cnd.ExactMatch("Готов")),
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Выйти")),
            ],
        },
        "ready": {
            RESPONSE: "Пожалуйста ожидайте начало игры",
            TRANSITIONS: [Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Выйти"))],
        },
    },
}

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


pipeline = Pipeline(
    greeting_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
    messenger_interface=interface,
)

config = load_config().chatsky

if __name__ == "__main__":
    pipeline.run()
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
    )
