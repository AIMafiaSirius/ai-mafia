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
    Message,
    MessageInitTypes,
    Pipeline,
)
from chatsky import Transition as Tr
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ai_mafia.config import load_config
from ai_mafia.db.models import RoomModel
from ai_mafia.db.routines import (
    add_room,
    add_user,
    exit_room,
    find_game_room,
    find_user,
    get_random_room,
    join_room,
    mark_user_as_ready,
    start_game,
)
from ai_mafia.tg_proxy import chatsky_web_api, chatsky_web_interface, send_room_is_ready_signal

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import PlayerModel, UserModel

load_dotenv()


def room_info_string(room: RoomModel):
    return f"""Данные по комнате:
Id: {room.room_id}
Название: {room.name}
Число участников: {len(room.list_players)}/10"""


class NewRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        name = ctx.last_request.text
        room_info = add_room(name)
        ctx.misc["room_info"] = room_info
        return room_info_string(room_info) + "\n\nПрисоединиться?"


class JoinRoomResponse(BaseResponse):
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


class CheckReadyProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        room = mark_user_as_ready(ctx.misc["user_info"].db_id, ctx.misc["room_info"].db_id)
        if room.is_room_ready():
            send_room_is_ready_signal(str(ctx.id))


class StartGameProcessing(BaseProcessing):
    """Implement game starting logic"""

    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        start_game(room_info.db_id)


class StartGameResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room_info: RoomModel = ctx.misc["room_info"]
        user_info: UserModel = ctx.misc["user_info"]
        player: PlayerModel = room_info.get_player(str(user_info.db_id))
        return f"""Игра началась!
Ваш номер: {player["number"]}
Ваша роль: {player["role"]}"""


with open("game_rules.json", encoding="utf8") as file:  # noqa: PTH123
    game_rules_data = json.load(file)

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
                Tr(dst=("get_rules"), cnd=CallbackCondition(query_string="instr_yes")),
                Tr(dst=("to_room_flow", "choose"), cnd=CallbackCondition(query_string="instr_no")),
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
            RESPONSE: game_rules_data["full_rules"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "game_roles": {
            RESPONSE: game_rules_data["roles"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "day_phase": {
            RESPONSE: game_rules_data["game_phase"]["day"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "voting_phase": {
            RESPONSE: game_rules_data["game_phase"]["voting"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "night_phase": {
            RESPONSE: game_rules_data["game_phase"]["night"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "start_and_end": {
            RESPONSE: game_rules_data["game_phase"]["game_start_and_end"],
            TRANSITIONS: [
                Tr(dst=("greeting_flow", "get_rules"), cnd=cnd.ExactMatch("Назад")),
            ],
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
                Tr(dst=("join_id"), cnd=cnd.All(cnd.ExactMatch("К случайной"), RandomRoomExistCondition())),
                Tr(
                    dst=("random_not_found"),
                    cnd=cnd.All(cnd.ExactMatch("К случайной"), cnd.Not(RandomRoomExistCondition())),
                ),
                Tr(
                    dst=("join_id"),
                    cnd=cnd.All(cnd.Not(cnd.ExactMatch("К случайной")), RoomExistCondition()),
                ),
                Tr(
                    dst="room_not_found",
                    cnd=cnd.All(cnd.Not(cnd.ExactMatch("К случайной")), cnd.Not(RoomExistCondition())),
                ),
                Tr(dst="choose", cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "random_not_found": {
            RESPONSE: "Сейчас нет открытых комнат. Создать новую?",
            TRANSITIONS: [
                Tr(dst="make", cnd=cnd.ExactMatch("Да")),
                Tr(dst="enter_id", cnd=cnd.ExactMatch("Назад")),
            ],
        },
        "join_id": {
            RESPONSE: JoinRoomResponse(),
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
            PRE_RESPONSE: {"call_syncronizer": CheckReadyProcessing()},
            RESPONSE: "Пожалуйста, ожидайте начало игры",
            PRE_TRANSITION: {"exit_room": ExitRoomProcessing()},
            TRANSITIONS: [
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Выйти")),
                Tr(dst=("in_game", "start_node"), cnd=cnd.ExactMatch("_ready_")),
            ],
        },
    },
    "in_game": {
        "start_node": {
            PRE_RESPONSE: {"init_game": StartGameProcessing()},
            RESPONSE: StartGameResponse(),
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
