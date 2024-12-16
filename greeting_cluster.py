from chatsky import (
    PRE_RESPONSE,
    RESPONSE,
    TRANSITIONS,
    Context,
    Pipeline,
    Transition as Tr,
    conditions as cnd,
    responses as rsp,
    destinations as dst,
    BaseCondition,
    BaseResponse,
    MessageInitTypes,
)
from chatsky.processing import ModifyResponse
import random

from uuid import uuid4

class Room:

    def __init__(self, name):
        self.name = name
        self.players = []
    

map_room = {}

class NewRoom(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        curId = uuid4()
        name = ctx.last_request.text
        map_room[curId] = Room(name)
        return "Id: " + str(curId) + '\n' + "Комната: " + str(name) + '\n' + "Присоединиться?"


class RandomID(ModifyResponse):
    async def modified_response(self, _: BaseResponse, __: Context) -> MessageInitTypes:
        if len(map_room) == 0:
            return "К сожалению сейчас нет открытых игр, попробуйте позже или создайте свою"
        curId, name = random.choice(map_room)
        return "Id: " + str(curId) + '\n' + "Комната: " + str(name) + '\n' + "Присоединиться?"


greeting_script = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))],
        },
        "greeting_node": {
            RESPONSE: "Привет! Нужна ли вам инструкция по игре?",
            TRANSITIONS: [
                Tr(dst=("instruction"), cnd=cnd.ExactMatch("Да")),
                Tr(dst=("to_room_flow", "choose"), cnd=cnd.ExactMatch("Нет")),
            ],
        },
        "instruction": {
            RESPONSE: "...",
            TRANSITIONS: [Tr(dst=("to_room_flow", "choose"))],
        },
        "fallback_node": {
            RESPONSE: "К сожалению я не могу обработать такую команду, введите другую",
            TRANSITIONS: [Tr(dst=dst.Backward())],
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
            RESPONSE: NewRoom(),
            TRANSITIONS: [
                Tr(dst=("choose"), cnd=cnd.ExactMatch("Назад")),
                Tr(dst=("in_room_flow", "ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
        "enter_id": {
            RESPONSE: "Введите id комнаты, или присоединитесь к случайной",
            TRANSITIONS: [
                Tr(dst=("random_id"), cnd=cnd.ExactMatch("К случайной")),
            ],
        },
        "random_id": {
            PRE_RESPONSE: {"random_id_service": RandomID()},
            RESPONSE: "",
            TRANSITIONS: [
                Tr(dst=("in_room_flow", "ready"), cnd=cnd.ExactMatch("Да")),
            ],
        },
    },
    "in_room_flow": {
        "ready": {
            RESPONSE: "Нажмите готов для подтверждения игры",
        },
    },
}

pipeline = Pipeline(
    greeting_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
