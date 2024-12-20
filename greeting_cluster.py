import json
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
    MessageInitTypes,
    Pipeline,
)
from chatsky import Transition as Tr
from dotenv import load_dotenv

from ai_mafia.config import load_config
from ai_mafia.db.models import RoomModel
from ai_mafia.db.routines import add_game_room, add_user, find_game_room, find_user, get_random_room, join_room
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
Число участников: {len(room.list_users)}/10"""


class NewRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        name = str(ctx.last_request.text)
        room = add_game_room(name)
        return room_info_string(room)


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


class GreetingResponse(BaseResponse):
    """
    Greet and provide info about user
    """

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        return f"Привет, {user_info.tg_nickname}! Вам нужны правила игры?"


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


with open("game_rules.json") as file:  # noqa: PTH123
    data = json.load(file)

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
                Tr(dst=("get_rules"), cnd=cnd.ExactMatch("Да")),
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Нет")),
            ],
        },
        "get_rules": {
            RESPONSE: "Вам нужны полные правила или какой-то определённый раздел?",
            TRANSITIONS: [
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("rules_flow", "game_rules"), cnd=cnd.ExactMatch("Полные")),
                Tr(dst=("rules_flow", "game_roles"), cnd=cnd.ExactMatch("Роли")),
                Tr(dst=("rules_flow", "day_phase"), cnd=cnd.ExactMatch("День")),
                Tr(dst=("rules_flow", "voting_phase"), cnd=cnd.ExactMatch("Голосование")),
                Tr(dst=("rules_flow", "night_phase"), cnd=cnd.ExactMatch("Ночь")),
                Tr(dst=("rules_flow", "start_and_end"), cnd=cnd.ExactMatch("Начало и конец игры")),
            ],
        },
    },
    "rules_flow": {
        "game_rules": {
            RESPONSE: data["full_rules"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ]
        },
        "game_roles": {
            RESPONSE: data["roles"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ]
        },
        "day_phase": {
            RESPONSE: data["game_phase"]["day"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ]
        },
        "voting_phase": {
            RESPONSE: data["game_phase"]["voting"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ]
        },
        "night_phase": {
            RESPONSE: data["game_phase"]["night"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ]
        },
        "start_and_end": {
            RESPONSE: data["game_phase"]["game_start_and_end"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ]
        }
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
            RESPONSE: "Нет открытых комнат. Создать новую?",
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
        "room_not_found": {RESPONSE: "комната с таким ID не найдена"},
    },
    "in_room_flow": {
        "not_ready": {
            PRE_RESPONSE: {"join_room": JoinRoomProcessing()},
            RESPONSE: "Вы присоединились к комнате. Введите 'Готов', если готовы начать",
            TRANSITIONS: [
                Tr(dst=("waiting"), cnd=cnd.ExactMatch("Готов")),
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Выйти")),
            ],
        },
        "waiting": {
            PRE_RESPONSE: {"call_syncronizer": CallSynchronizerProcessing()},
            RESPONSE: "Пожалуйста, ожидайте начало игры",
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
