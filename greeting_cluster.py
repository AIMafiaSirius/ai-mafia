from typing import TYPE_CHECKING

import chatsky.conditions as cnd
import chatsky.destinations as dst
import uvicorn
from chatsky import (
    PRE_RESPONSE,
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
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ai_mafia.config import load_config
from ai_mafia.db.models import RoomModel
from ai_mafia.db.routines import add_room, add_user, exit_room, find_game_room, find_user, get_random_room, join_room
from ai_mafia.sync import send_ready_signal
from ai_mafia.tg_proxy import chatsky_web_api, chatsky_web_interface

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import UserModel

load_dotenv()


def room_info_string(room: RoomModel):
    return f"""Данные по комнате:
Id: {room.room_id}
Название: {room.name}
Число участников: {len(room.list_players)}/10"""


class NewRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        name = ctx.last_request.text
        room = add_room(name)
        return room_info_string(room) + "\n\nПрисоединиться?"


class JoinRandomRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room: RoomModel = ctx.misc["room_info"]
        return room_info_string(room) + "\n\nПрисоединиться?"


class RandomRoomExistCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room = get_random_room()
        if room is not None:
            ctx.misc["room_info"] = room
            return True
        return False


class RoomExistCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room = find_game_room(ctx.last_request.text)
        if room is not None:
            ctx.misc["room_info"] = room
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


class CallbackCondition(BaseCondition):
    query_string: str

    async def call(self, ctx: Context):
        upd: tg.Update = ctx.last_request.original_message
        if upd.callback_query is None:
            return False
        return upd.callback_query.data == self.query_string


class GreetingResponse(BaseResponse):
    """
    Greet and provide info about user
    """

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        text = f"Привет, {user_info.tg_nickname}! Вам нужна инструкция по игре?"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Да", callback_data="instr_yes"),
                    InlineKeyboardButton("Нет", callback_data="instr_no"),
                ]
            ]
        )
        return Message(text=text, reply_markup=keyboard)


class CallSynchronizerProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        send_ready_signal(user_info.db_id, room_info.db_id, ctx.id)


class JoinRoomProcessing(BaseProcessing):
    """Implement room joining logic"""

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        join_room(user_info.db_id, room_info.db_id)


class ExitRoomProcessing(BaseProcessing):
    """Implement room exiting logic"""

    async def call(self, ctx: Context):
        if ctx.last_request.text == "Выйти":
            user_info: UserModel = ctx.misc["user_info"]
            room_info: RoomModel = ctx.misc["room_info"]
            exit_room(user_info.db_id, room_info.db_id)


greeting_script = {
    "global_flow": {
        "start_node": {},
        "fallback_node": {
            RESPONSE: "К сожалению, я не могу обработать такую команду, введите другую",
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
                Tr(dst=("instruction"), cnd=CallbackCondition(query_string="instr_yes")),
                Tr(dst=("to_room_flow", "choose"), cnd=CallbackCondition(query_string="instr_no")),
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
                Tr(
                    dst=("in_room_flow", "not_ready"),
                    cnd=cnd.All(cnd.Not(cnd.ExactMatch("К случайной")), RoomExistCondition()),
                ),
                Tr(
                    dst="room_not_found",
                    cnd=cnd.All(cnd.Not(cnd.ExactMatch("К случайной")), cnd.Not(RoomExistCondition())),
                ),
            ],
        },
        "random_not_found": {
            RESPONSE: "Сейчас нет открытых комнат. Создать новую?",
            TRANSITIONS: [
                Tr(dst="make", cnd=cnd.ExactMatch("Да")),
                Tr(dst="enter_id", cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "random_id": {
            RESPONSE: JoinRandomRoomResponse(),
            TRANSITIONS: [
                Tr(dst="choose", cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
        "room_not_found": {
            RESPONSE: "Комната с таким ID не найдена",
            TRANSITIONS: [Tr(dst=("enter_id"))],
        },
    },
    "in_room_flow": {
        "not_ready": {
            PRE_RESPONSE: {"join_room": JoinRoomProcessing()},
            RESPONSE: "Вы присоединились к комнате. Введите 'Готов', если готовы начать",
            PRE_TRANSITION: {"exit_room": ExitRoomProcessing()},
            TRANSITIONS: [
                Tr(dst=("waiting"), cnd=cnd.ExactMatch("Готов")),
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Выйти")),
            ],
        },
        "waiting": {
            PRE_RESPONSE: {"call_syncronizer": CallSynchronizerProcessing()},
            RESPONSE: "Пожалуйста, ожидайте начало игры",
            PRE_TRANSITION: {"exit_room": ExitRoomProcessing()},
            TRANSITIONS: [
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Выйти")),
                Tr(dst=("in_game", "start_node"), cnd=cnd.ExactMatch("_ready_")),
            ],
        },
    },
}


pipeline = Pipeline(
    greeting_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("global_flow", "fallback_node"),
    messenger_interface=chatsky_web_interface,
)

config = load_config().chatsky

if __name__ == "__main__":
    pipeline.run()
    uvicorn.run(
        chatsky_web_api,
        host=config.host,
        port=config.port,
    )
