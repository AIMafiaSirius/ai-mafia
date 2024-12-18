import os
from typing import TYPE_CHECKING

from chatsky import (
    PRE_RESPONSE,
    PRE_TRANSITION,
    RESPONSE,
    TRANSITIONS,
    BaseProcessing,
    BaseResponse,
    Context,
    MessageInitTypes,
    Pipeline,
)
from chatsky import (
    Transition as Tr,
)
from chatsky import (
    conditions as cnd,
)
from chatsky import (
    destinations as dst,
)
from chatsky.messengers.telegram import LongpollingInterface
from chatsky.processing import ModifyResponse
from dotenv import load_dotenv

from ai_mafia.db.routines import add_game_room, add_user, find_user, get_random_room

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import UserModel

load_dotenv()


class NewRoom(ModifyResponse):
    async def modified_response(self, _: BaseResponse, ctx: Context) -> MessageInitTypes:
        name = str(ctx.last_request.text)
        room = add_game_room(name)
        return f"Данные по комнате:\
        \nId: {room.room_id}\
        \nНазвание: {name}\
        \nЧисло участников: {len(room.list_users)}/10"


class RandomGameRoom(ModifyResponse):
    async def modified_response(self, _: BaseResponse, __: Context) -> MessageInitTypes:
        room = get_random_room()
        if room is None:
            return "К сожалению сейчас нет открытых игр, создайте свою комнату или попробуйте позже."
        return f"Данные по комнате:\
            \nId: {room.room_id}\
            \nНазвание: {room.name}\
            \nЧисло участников: {len(room.list_users)}/10"


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
            PRE_RESPONSE: {"new_room_service": NewRoom()},
            RESPONSE: "Присоединиться?",
            TRANSITIONS: [
                Tr(dst=("choose"), cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
        "enter_id": {
            RESPONSE: "Введите ID комнаты, или присоединитесь к случайной",
            TRANSITIONS: [
                Tr(dst=("random_id"), cnd=cnd.ExactMatch("К случайной")),
            ],
        },
        "random_id": {
            PRE_RESPONSE: {"random_id_service": RandomGameRoom()},
            RESPONSE: "Присоединиться?",
            TRANSITIONS: [
                Tr(dst=("choose"), cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("in_room_flow", "not_ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
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

interface = LongpollingInterface(token=os.environ["TG_TOKEN"])

pipeline = Pipeline(
    greeting_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("global_flow", "fallback_node"),
    messenger_interface=interface,
)

if __name__ == "__main__":
    pipeline.run()
