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
from ai_mafia.constants import N_PLAYERS, NUM_PLAYERS
from ai_mafia.db.models import RoomModel
from ai_mafia.db.routines import (
    add_room,
    add_user,
    exit_room,
    find_game_room,
    find_user,
    get_random_room,
    join_room,
    murder,
    send_player_message,
    set_player_state,
    shoot,
    start_game,
    update_last_words,
)
from ai_mafia.tg_proxy import chatsky_web_api, chatsky_web_interface, send_signal

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import PlayerModel, UserModel

load_dotenv()


def room_info_string(room: RoomModel):
    return f"""Данные по комнате:
Id: {room.room_id}
Название: {room.name}
Число участников: {len(room.list_players)}/10"""


class FallbackResponse(BaseResponse):
    async def call(self, ctx: Context):
        txt = ctx.last_request.text
        return f"К сожалению, я не могу обработать команду: {txt}"


class FromRulesDestination(BaseDestination):
    async def call(self, ctx: Context):
        return ctx.misc["from_where"]


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


class GetRulesProcessing(BaseProcessing):
    """Implement rule buttons logic"""

    from_where: tuple

    async def call(self, ctx: Context):
        upd: tg.Update = ctx.last_request.original_message
        if upd is not None and upd.callback_query.data == "get_rules":
            ctx.misc["from_where"] = self.from_where


class CreateRoomResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="step_backward")]])
        return Message(text="Введите название для комнаты", reply_markup=keyboard)


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


class RandomRoomCreatedCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room = get_random_room()
        if room is not None and room.room_state == "created":
            ctx.misc["room_info"] = room
            return True
        return False


class RoomCreatedCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        room = find_game_room(ctx.last_request.text)
        if room is not None and room.room_state == "created":
            ctx.misc["room_info"] = room
            return True
        return False


class CallbackCondition(BaseCondition):
    query_string: str

    async def call(self, ctx: Context):
        upd: tg.Update | None = ctx.last_request.original_message
        if upd is None or upd.callback_query is None:
            return False
        return upd.callback_query.data == self.query_string


class JoinRoomProcessing(BaseProcessing):
    """Implement room joining logic"""

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        if room_info.get_player(str(user_info.db_id)) is None:
            join_room(user_info.db_id, room_info.db_id, ctx.id, ctx.misc["chat_id"])


class ExitRoomProcessing(BaseProcessing):
    """Implement room exiting logic"""

    async def call(self, ctx: Context):
        upd: tg.Update | None = ctx.last_request.original_message
        if upd is not None and upd.callback_query.data == "leave":
            user_info: UserModel = ctx.misc["user_info"]
            room_info: RoomModel = ctx.misc["room_info"]
            exit_room(user_info.db_id, room_info.db_id)
            ctx.misc["room_info"] = None


class NotReadyProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        upd: tg.Update | None = ctx.last_request.original_message
        if upd is not None and upd.callback_query.data == "not_ready":
            user_info: UserModel = ctx.misc["user_info"]
            room_info: RoomModel = ctx.misc["room_info"]
            set_player_state(user_info.db_id, room_info.db_id, "not_ready")
            ctx.misc["room_info"] = find_game_room(room_info.room_id)


class CheckReadyProcessing(ModifyResponse):
    async def modified_response(self, original_response: BaseResponse, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        room = set_player_state(user_info.db_id, room_info.db_id, "ready")
        if room.is_room_ready(N_PLAYERS):
            send_signal(find_game_room(room_info.room_id), "_ready_")
            return "Мы вас ждали!"
        return await original_response(ctx)


class StartGameProcessing(ModifyResponse):
    """Implement game starting logic"""

    async def modified_response(self, original_response: BaseResponse, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        if ctx.id == room.list_players[0].ctx_id:
            start_game(room.db_id)
            send_signal(find_game_room(room_info.room_id))
        return await original_response(ctx)


class StartGameResponse(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        room: RoomModel = find_game_room(room_info.room_id)
        ctx.misc["room_info"] = room
        player_info: PlayerModel = room.get_player(str(user_info.db_id))
        return f"""Игра началась!
Ваш номер: {player_info.number}
Ваша роль: {player_info.role}"""


with open("game_rules.json", encoding="utf8") as file:  # noqa: PTH123
    game_rules_data = json.load(file)


class ShootingResponse(BaseResponse):
    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        player_info: PlayerModel = room_info.get_player(str(user_info.db_id))
        if ctx.id == room_info.list_players[0].ctx_id:
            send_signal(find_game_room(room_info.room_id), timer=10)
        if player_info.role in ("мафия", "дон") and player_info.state == "alive":
            return "Наступает ночь! Напишите номер игрока, в которого будете стрелять. У вас 10 секунд"
        return "Наступает ночь! Мафия выбирает, кого убить"


class ShootingProcessing(BaseProcessing):
    """Implement shooting logic"""

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        player_info: PlayerModel = room_info.get_player(str(user_info.db_id))
        request = ctx.last_request.text
        if player_info.role in ("мафия", "дон") and request in NUM_PLAYERS:
            shoot(room_db_id=ctx.misc["room_info"].db_id, i=int(request) - 1)


class ShootCondition(BaseCondition):
    async def call(self, ctx: Context) -> MessageInitTypes:
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        return room_info.get_player(str(user_info.db_id)).role in ("мафия", "дон")


class CheckResponse(BaseResponse):
    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        player_info: PlayerModel = room_info.get_player(str(user_info.db_id))
        if ctx.id == room_info.list_players[0].ctx_id:
            send_signal(find_game_room(room_info.room_id), timer=10)
        if player_info.role == "комиссар" and player_info.state == "alive":
            return "Вы - комиссар. Напишите номер игрока, которого хотите проверить. У вас 10 секунд"
        if player_info.role == "дон" and player_info.state == "alive":
            return "Вы - дон мафии. Напишите номер игрока, которого хотите проверить на комиссарство. У вас 10 секунд"
        return "Дон и комиссар делают проверки"


class IsCom(BaseCondition):
    async def call(self, ctx: Context) -> bool:
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        player_info: PlayerModel = room_info.get_player(str(user_info.db_id))
        return player_info.role == "комиссар"


class IsDon(BaseCondition):
    async def call(self, ctx: Context) -> bool:
        user_info: UserModel = ctx.misc["user_info"]
        room_info: RoomModel = ctx.misc["room_info"]
        player_info: PlayerModel = room_info.get_player(str(user_info.db_id))
        return player_info.role == "дон"


class ComsCheckResponse(BaseResponse):
    async def call(self, ctx: Context):
        request = ctx.last_request.text
        if request in NUM_PLAYERS:
            num = int(request)
            role = ctx.misc["room_info"].list_players[num - 1].role
            color = "красный"
            if role in ("мафия", "дон"):
                color = "чёрный"
            return f"Этот игрок {color}"
        return "Напишите номер игрока, которого хотите проверить"


class DonsCheckResponse(BaseResponse):
    async def call(self, ctx: Context):
        request = ctx.last_request.text
        if request in NUM_PLAYERS:
            num = int(request)
            role = ctx.misc["room_info"].list_players[num - 1].role
            is_com = "не комиссар"
            if role == "комиссар":
                is_com = "комиссар"
            return f"Этот игрок {is_com}"
        return "Напишите номер игрока, которого хотите проверить"


class EndNightProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        if ctx.id == room_info.list_players[0].ctx_id:
            if murder(room_info.room_id):
                send_signal(find_game_room(room_info.room_id), "_kill_")
            else:
                send_signal(find_game_room(room_info.room_id))


class EndNightResponse(BaseResponse):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        pre_dead_player: PlayerModel = room.get_pre_dead_player()
        if pre_dead_player is None:
            return "В эту ночь мафия никого не убила"
        return f"""В эту ночь мафия убила игрока номер {pre_dead_player.number}"""


class DeadSpeechProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        player: PlayerModel = room.get_pre_dead_player()
        if ctx.id == player.ctx_id:
            update_last_words(room.room_id, ctx.last_request.text)
            send_signal(room=room, timer=10)


class DeadSpeechResponse(BaseResponse):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        player: PlayerModel = room.get_pre_dead_player()

        if ctx.id == player.ctx_id:
            return "Ваше слово:"
        if room.last_words is None:
            return f"Сейчас будет речь игрока {player.number}"
        return room.last_words


class AreYouPreDeadCondition(BaseCondition):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        player: PlayerModel = room.get_pre_dead_player()

        return ctx.id == player.ctx_id


class ReadDeadSpeechResponse(BaseResponse):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        player: PlayerModel = room.get_pre_dead_player()

        return f"У игрока {player.number} есть прощальная минута."


class LastWordsProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        user_info: UserModel = ctx.misc["user_info"]
        update_last_words(room_info.room_id, ctx.last_request.text)

        room = find_game_room(room_info.room_id)
        send_player_message(room=room, user_id=str(user_info.db_id), msg="_speech_")


class ReadLastWordsResponse(BaseResponse):
    async def call(self, ctx: Context):
        room_info: RoomModel = ctx.misc["room_info"]
        room = find_game_room(room_info.room_id)
        return room.last_words


class LastWordsResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Закончить речь", "_skip_")]])
        return Message(text="Ваше слово:", reply_markup=keyboard)


class LastMinuteResponse(BaseResponse):
    async def call(self, _: Context):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ ОК", "ok")]])
        return Message(text="У вас есть прощальная минута", reply_markup=keyboard)


greeting_script = {
    "global_flow": {
        "fallback_node": {
            RESPONSE: FallbackResponse(),
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
                    cnd=cnd.All(CallbackCondition(query_string="to_random"), RandomRoomCreatedCondition()),
                ),
                Tr(
                    dst=("random_not_found"),
                    cnd=cnd.All(CallbackCondition(query_string="to_random"), cnd.Not(RandomRoomCreatedCondition())),
                ),
                Tr(
                    dst=("join_id"),
                    cnd=cnd.All(
                        cnd.All(
                            cnd.Not(CallbackCondition(query_string="to_random")),
                            cnd.Not(CallbackCondition(query_string="step_backward")),
                        ),
                        RoomCreatedCondition(),
                    ),
                ),
                Tr(
                    dst="room_not_found",
                    cnd=cnd.All(
                        cnd.Not(CallbackCondition(query_string="to_random")),
                        cnd.Not(CallbackCondition(query_string="step_backward")),
                        cnd.Not(RoomCreatedCondition()),
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
                Tr(dst=("in_room_flow", "not_ready"), cnd=CallbackCondition(query_string="join")),
                Tr(dst=dst.Previous(), cnd=CallbackCondition(query_string="step_backward")),
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
                "not_ready": NotReadyProcessing(),
            },
            TRANSITIONS: [
                Tr(dst=("to_room_flow", "choose"), cnd=CallbackCondition(query_string="leave")),
                Tr(dst="not_ready", cnd=CallbackCondition(query_string="not_ready")),
                Tr(dst=("rules_flow", "get_rules"), cnd=CallbackCondition(query_string="get_rules")),
                Tr(dst=("in_game_flow", "start_node"), cnd=cnd.ExactMatch("_ready_")),
            ],
        },
    },
    "in_game_flow": {
        "fallback_node": {
            RESPONSE: "Пожалуйста, дождитесь оставшихся игроков",
            TRANSITIONS: [Tr(dst=dst.Previous())],
        },
        "start_node": {
            PRE_RESPONSE: {"init_game": StartGameProcessing()},
            RESPONSE: StartGameResponse(),
            TRANSITIONS: [Tr(dst=("shooting_phase"))],
        },
        "shooting_phase": {
            RESPONSE: ShootingResponse(),
            PRE_TRANSITION: {"shoot": ShootingProcessing()},
            TRANSITIONS: [
                Tr(dst=("checks_phase"), cnd=cnd.ExactMatch("_skip_")),
                Tr(dst=("post_shooting_phase"), cnd=ShootCondition()),
            ],
        },
        "post_shooting_phase": {
            RESPONSE: "Ждём ходы от остальных игроков чёрной команды",
            TRANSITIONS: [Tr(dst=("checks_phase"), cnd=cnd.ExactMatch("_skip_"))],
        },
        "checks_phase": {
            RESPONSE: CheckResponse(),
            TRANSITIONS: [
                Tr(dst=("coms_check"), cnd=IsCom()),
                Tr(dst=("dons_check"), cnd=IsDon()),
                Tr(dst=("end_of_night"), cnd=cnd.ExactMatch("_skip_")),
            ],
        },
        "coms_check": {
            RESPONSE: ComsCheckResponse(),
            TRANSITIONS: [
                Tr(dst=("post_check_phase"), cnd=cnd.Not(cnd.ExactMatch("_skip_"))),
                Tr(dst=("end_of_night"), cnd=cnd.ExactMatch("_skip_")),
            ],
        },
        "dons_check": {
            RESPONSE: DonsCheckResponse(),
            TRANSITIONS: [
                Tr(dst=("post_check_phase"), cnd=cnd.Not(cnd.ExactMatch("_skip_"))),
                Tr(dst=("end_of_night"), cnd=cnd.ExactMatch("_skip_")),
            ],
        },
        "post_check_phase": {
            RESPONSE: "Пожалуйста, дождитесь окончание таймера",
            TRANSITIONS: [Tr(dst=("end_of_night"), cnd=cnd.ExactMatch("_skip_"))],
        },
        "end_of_night": {
            PRE_RESPONSE: {"check_pre_dead": EndNightProcessing()},
            RESPONSE: EndNightResponse(),
            TRANSITIONS: [
                Tr(dst=("day"), cnd=cnd.ExactMatch("_skip_")),
                Tr(dst=("read_dead_speech"), cnd=cnd.All(cnd.ExactMatch("_kill_"), cnd.Not(AreYouPreDeadCondition()))),
                Tr(dst=("write_dead_speech"), cnd=cnd.All(cnd.ExactMatch("_kill_"), AreYouPreDeadCondition())),
            ],
        },
        "write_dead_speech": {
            RESPONSE: LastMinuteResponse(),
            PRE_TRANSITION: {"speech": DeadSpeechProcessing()},
            TRANSITIONS: [
                Tr(dst=("day"), cnd=cnd.ExactMatch("_skip_")),
                Tr(dst=("writing_cycle"), cnd=cnd.Not(cnd.ExactMatch("_skip_"))),
            ],
        },
        "writing_cycle": {
            RESPONSE: "ваше слово:",
            PRE_TRANSITION: {"save_last_words": LastWordsProcessing()},
            TRANSITIONS: [
                Tr(dst=("day"), cnd=cnd.Any(CallbackCondition(query_string="_skip_"), cnd.ExactMatch("_skip_"))),
                Tr(dst=("writing_cycle"), cnd=cnd.Not(CallbackCondition(query_string="_skip_"))),
            ],
        },
        "read_dead_speech": {
            RESPONSE: ReadDeadSpeechResponse(),
            TRANSITIONS: [
                Tr(dst=("day"), cnd=cnd.ExactMatch("_skip_")),
                Tr(dst=("reading_cycle"), cnd=cnd.ExactMatch("_speech_")),
            ],
        },
        "reading_cycle": {
            RESPONSE: ReadLastWordsResponse(),
            TRANSITIONS: [
                Tr(dst=("day"), cnd=cnd.ExactMatch("_skip_")),
                Tr(dst=("reading_cycle"), cnd=cnd.ExactMatch("_speech_")),
            ],
        },
        "day": {
            RESPONSE: "Наступил день",
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
