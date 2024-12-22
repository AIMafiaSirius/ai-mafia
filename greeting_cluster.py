import json
from random import randint
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
    BaseDestination,
    BaseProcessing,
    BaseResponse,
    Context,
    Message,
    MessageInitTypes,
    Pipeline,
)
from chatsky import Transition as Tr
from chatsky.processing import ModifyResponse
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
)
from ai_mafia.tg_proxy import chatsky_web_api, chatsky_web_interface, send_room_is_ready_signal

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import UserModel

load_dotenv()


def room_info_string(room: RoomModel):
    return f"""Данные по комнате:
Id: {room.room_id}
Название: {room.name}
Число участников: {len(room.list_players)}/10"""


def shuffle_list(arr: list):
    for i in range(len(arr)):
        j = randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


class NewRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        name = ctx.last_request.text
        room = add_room(name)
        ctx.misc["room_info"] = room

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Да", callback_data="ok"),
                    InlineKeyboardButton("⬅️ Назад", callback_data="step_backward"),
                ]
            ]
        )
        return Message(text=room_info_string(room) + "\n\nВсё верно?", reply_markup=keyboard)


class JoinRoomResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room: RoomModel = ctx.misc["room_info"]

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⬅️ Назад", callback_data="step_backward"),
                    InlineKeyboardButton("✅ Да", callback_data="join"),
                ]
            ]
        )
        return Message(text=room_info_string(room) + "\n\nПрисоединиться?", reply_markup=keyboard)


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
        ctx.misc["chat_id"] = tg_info.effective_chat.id


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
                    InlineKeyboardButton("✅ Да", callback_data="get_rules"),
                    InlineKeyboardButton("❌ Нет", callback_data="instr_no"),
                ]
            ]
        )
        return Message(text=text, reply_markup=keyboard)


class ShowRulesResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📝 Полные правила", callback_data="full_rules"),
                ],
                [
                    InlineKeyboardButton("🎭 Роли", callback_data="game_roles"),
                ],
                [
                    InlineKeyboardButton("🌅 День", callback_data="day_phase"),
                    InlineKeyboardButton("🗣️ Голосование", callback_data="voting_phase"),
                    InlineKeyboardButton("🌃 Ночь", callback_data="night_phase"),
                ],
                [InlineKeyboardButton("🕹️ Начало и конец игры", callback_data="start_and_end")],
                [
                    InlineKeyboardButton("⬅️ Назад", callback_data="step_backward"),
                ],
            ]
        )
        return Message(text="Выберите раздел правил, который хотите увидеть", reply_markup=keyboard)


class RuleResponse(BaseResponse):
    name: str

    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="step_backward")]])
        return Message(text=game_rules_data[self.name], reply_markup=keyboard)


class JoinRoomProcessing(BaseProcessing):
    """Implement room joining logic"""

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        join_room(user_info.db_id, room_info.db_id, ctx.id, ctx.misc["chat_id"])


class GetRulesProcessing(BaseProcessing):
    """Implement get_rules button logic"""

    from_where: tuple

    async def call(self, ctx: Context):
        upd: tg.Update = ctx.last_request.original_message
        if upd.callback_query.data == "get_rules":
            ctx.misc["from_where"] = self.from_where


class ExitRoomProcessing(BaseProcessing):
    """Implement room exiting logic"""

    async def call(self, ctx: Context):
        upd: tg.Update = ctx.last_request.original_message
        if upd.callback_query.data == "leave":
            user_info: UserModel = ctx.misc["user_info"]
            room_info: RoomModel = ctx.misc["room_info"]
            exit_room(user_info.db_id, room_info.db_id)


class CheckReadyProcessing(ModifyResponse):
    async def modified_response(self, original_response: BaseResponse, ctx: Context):
        room = mark_user_as_ready(ctx.misc["user_info"].db_id, ctx.misc["room_info"].db_id)
        if room.is_room_ready():
            send_room_is_ready_signal(ctx.misc["room_info"].room_id)
            return "Мы вас ждали!"
        return await original_response(ctx)


class ChooseRoomResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📝 Правила игры", callback_data="get_rules")],
                [
                    InlineKeyboardButton("⚙️ Создать", callback_data="create_room"),
                    InlineKeyboardButton("🚪 Присоединиться", callback_data="join_room"),
                ],
            ]
        )
        return Message(text="Вы хотите присоединться к комнате или создать новую?", reply_markup=keyboard)


class AreYouReadyResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📝 Правила игры", callback_data="get_rules")],
                [
                    InlineKeyboardButton("🚪 Выйти", callback_data="leave"),
                    InlineKeyboardButton("✅ Готов", callback_data="ready"),
                ],
            ]
        )
        text = 'Вы присоединились к комнате. Нажмите на кнопку "готов", когда будете готовы начать игру.'
        return Message(text=text, reply_markup=keyboard)


class EnterRoomResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🎲 К случайной", callback_data="to_random"),
                ],
                [InlineKeyboardButton("⬅️ Назад", callback_data="step_backward")],
            ]
        )
        return Message(text="Присоединитесь к случайной комнате, либо введите ID", reply_markup=keyboard)


class RoomNotFoundResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⬅️ Назад", callback_data="step_backward"),
                ]
            ]
        )
        return Message(text="Комната с таким ID не найдена", reply_markup=keyboard)


class RandomNotFoundResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Да", callback_data="create"),
                    InlineKeyboardButton("⬅️ Назад", callback_data="step_backward"),
                ]
            ]
        )
        return Message(text="Сейчас нет открытых комнат. Создать новую?", reply_markup=keyboard)


class WaitingStartResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📝 Правила игры", callback_data="get_rules")],
                [
                    InlineKeyboardButton("🚪 Выйти", callback_data="leave"),
                    InlineKeyboardButton("❌ Не готов", callback_data="not_ready"),
                ],
            ]
        )
        return Message(text="Пожалуйста, ожидайте начала игры", reply_markup=keyboard)


class FallBackResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="step_backward")]])
        return Message(text="К сожалению, я не могу обработать эту команду", reply_markup=keyboard)


class CreateRoomResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="step_backward")]])
        return Message(text="Введите название для комнаты", reply_markup=keyboard)


with open("game_rules.json", encoding="utf8") as file:  # noqa: PTH123
    game_rules_data = json.load(file)


class FallbackResponse(BaseResponse):
    async def call(self, ctx: Context):
        txt = ctx.last_request.text
        return f"К сожалению, я не могу обработать команду: {txt}"


class FromRulesDestination(BaseDestination):
    async def call(self, ctx: Context):
        return ctx.misc["from_where"]


greeting_script = {
    "global_flow": {
        "fallback_node": {
            RESPONSE: FallBackResponse(),
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
            PRE_TRANSITION: {"get_rules": GetRulesProcessing(from_where=("greeting_flow", "greeting_node"))},
            TRANSITIONS: [
                Tr(dst=("rules_flow", "get_rules"), cnd=CallbackCondition(query_string="get_rules")),
                Tr(dst=("to_room_flow", "choose"), cnd=CallbackCondition(query_string="instr_no")),
            ],
        },
    },
    "rules_flow": {
        "get_rules": {
            RESPONSE: ShowRulesResponse(),
            TRANSITIONS: [
                Tr(dst=FromRulesDestination(), cnd=CallbackCondition(query_string="step_backward")),
                Tr(dst="full_rules", cnd=CallbackCondition(query_string="full_rules")),
                Tr(dst="game_roles", cnd=CallbackCondition(query_string="game_roles")),
                Tr(dst="day_phase", cnd=CallbackCondition(query_string="day_phase")),
                Tr(dst="voting_phase", cnd=CallbackCondition(query_string="voting_phase")),
                Tr(dst="night_phase", cnd=CallbackCondition(query_string="night_phase")),
                Tr(dst="start_and_end", cnd=CallbackCondition(query_string="start_and_end")),
            ],
        },
        "full_rules": {
            RESPONSE: RuleResponse(name="full_rules"),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "game_roles": {
            RESPONSE: RuleResponse(name="roles"),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "day_phase": {
            RESPONSE: RuleResponse(name="day"),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "voting_phase": {
            RESPONSE: RuleResponse(name="voting"),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "night_phase": {
            RESPONSE: RuleResponse(name="night"),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "start_and_end": {
            RESPONSE: RuleResponse(name="game_start_and_end"),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
    },
    "to_room_flow": {
        "choose": {
            RESPONSE: ChooseRoomResponse(),
            PRE_TRANSITION: {"get_rules": GetRulesProcessing(from_where=("to_room_flow", "choose"))},
            TRANSITIONS: [
                Tr(dst=("enter_id"), cnd=CallbackCondition(query_string="join_room")),
                Tr(dst=("make"), cnd=CallbackCondition(query_string="create_room")),
                Tr(dst=("rules_flow", "get_rules"), cnd=CallbackCondition(query_string="get_rules")),
            ],
        },
        "make": {
            RESPONSE: CreateRoomResponse(),
            TRANSITIONS: [
                Tr(dst=("new"), cnd=cnd.Not(CallbackCondition(query_string="step_backward"))),
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "new": {
            RESPONSE: NewRoomResponse(),
            TRANSITIONS: [
                Tr(dst=("choose"), cnd=CallbackCondition(query_string="step_backward")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=CallbackCondition(query_string="ok")),
            ],
        },
        "enter_id": {
            RESPONSE: EnterRoomResponse(),
            TRANSITIONS: [
                Tr(
                    dst=("join_id"),
                    cnd=cnd.All(CallbackCondition(query_string="to_random"), RandomRoomExistCondition()),
                ),
                Tr(
                    dst=("random_not_found"),
                    cnd=cnd.All(CallbackCondition(query_string="to_random"), cnd.Not(RandomRoomExistCondition())),
                ),
                Tr(
                    dst=("join_id"),
                    cnd=cnd.All(
                        cnd.All(
                            cnd.Not(CallbackCondition(query_string="to_random")),
                            cnd.Not(CallbackCondition(query_string="step_backward")),
                        ),
                        RoomExistCondition(),
                    ),
                ),
                Tr(
                    dst="room_not_found",
                    cnd=cnd.All(
                        cnd.Not(CallbackCondition(query_string="to_random")),
                        cnd.Not(CallbackCondition(query_string="step_backward")),
                        cnd.Not(RoomExistCondition()),
                    ),
                ),
                Tr(dst="choose", cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "random_not_found": {
            RESPONSE: RandomNotFoundResponse(),
            TRANSITIONS: [
                Tr(dst="make", cnd=CallbackCondition(query_string="create")),
                Tr(dst="enter_id", cnd=CallbackCondition(query_string="step_backward")),
            ],
        },
        "join_id": {
            RESPONSE: JoinRoomResponse(),
            TRANSITIONS: [
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=CallbackCondition(query_string="join")),
            ],
        },
        "room_not_found": {
            RESPONSE: RoomNotFoundResponse(),
            TRANSITIONS: [Tr(dst=("enter_id"), cnd=CallbackCondition(query_string="step_backward"))],
        },
    },
    "in_room_flow": {
        "not_ready": {
            PRE_RESPONSE: {"join_room": JoinRoomProcessing()},
            RESPONSE: AreYouReadyResponse(),
            PRE_TRANSITION: {
                "get_rules": GetRulesProcessing(from_where=("in_room_flow", "not_ready")),
                "exit_room": ExitRoomProcessing(),
            },
            TRANSITIONS: [
                Tr(dst=("waiting"), cnd=CallbackCondition(query_string="ready")),
                Tr(dst=("to_room_flow", "choose"), cnd=CallbackCondition(query_string="leave")),
                Tr(dst=("rules_flow", "get_rules"), cnd=CallbackCondition(query_string="get_rules")),
            ],
        },
        "waiting": {
            PRE_RESPONSE: {"call_syncronizer": CheckReadyProcessing()},
            RESPONSE: WaitingStartResponse(),
            PRE_TRANSITION: {
                "get_rules": GetRulesProcessing(from_where=("in_room_flow", "waiting")),
                "exit_room": ExitRoomProcessing(),
            },
            TRANSITIONS: [
                Tr(dst=("to_room_flow", "choose"), cnd=CallbackCondition(query_string="leave")),
                Tr(dst="not_ready", cnd=CallbackCondition(query_string="not_ready")),
                Tr(dst=("rules_flow", "get_rules"), cnd=CallbackCondition(query_string="get_rules")),
                Tr(dst=("in_game", "start_node"), cnd=cnd.ExactMatch("_ready_")),
            ],
        },
    },
    "in_game": {
        "start_node": {
            # PRE_RESPONSE: {"init_game": StartGameProcessing()},
            RESPONSE: "Игра началась",
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
