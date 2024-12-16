from chatsky import (
    TRANSITIONS,
    RESPONSE,
    Context,
    Message,
    Pipeline,
    Transition as Tr,
    conditions as cnd,
    responses as rsp,
    destinations as dst,
    BaseResponse,
    MessageInitTypes,
    AnyResponse,
    AbsoluteNodeLabel,
)
from typing import Union
import re

from uuid import uuid4

class Room:

    def __init__(self, name):
        self.name = name
        self.players = []
    

map_room = {}

class new_room(BaseResponse):
    async def call(self, ctx: Context) -> MessageInitTypes:
        curId = uuid4()
        request = ctx.last_request.text
        map_room[curId] = Room(request)
        return str(curId) + ' ' + str(request)


mafia_script = {
    "global_flow": {
        "start_node": {},
        "fallback_node": {
            RESPONSE: "К сожалению я не могу обработать такую команду, введите другую",
            TRANSITIONS: [Tr(dst=dst.Backward())]
            # this transition is unconditional
        },
    },
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))]
            # start node handles the initial handshake (command /start)
        },
        "greeting_node": {
            RESPONSE: "Привет! Нужна ли вам инструкция по игре?",
            TRANSITIONS: [Tr(dst=("game_start_node"), cnd=cnd.ExactMatch("Да"))],
            TRANSITIONS: [Tr(dst=("room_flow", "choose"), cnd=cnd.ExactMatch("Нет"))],
        },
        "instruction": {
            # RESPONSE: "...",
            TRANSITIONS: [Tr(dst=("room_flow", "choose"))],
        },
    },
    "room_flow": {
        "choose": {
            RESPONSE: "Создай комнату или присоединись к существующей",
            TRANSITIONS: [Tr(dst=("enter_id"), cnd=cnd.ExactMatch("Присоединиться"))],
            TRANSITIONS: [Tr(dst=("make"), cnd=cnd.ExactMatch("Создать"))],
        },
        "make": {
            RESPONSE: "Введите название для комнаты",
            TRANSITIONS: [Tr(dst=("new"))],
        },
        "new": {
            RESPONSE: new_room(),
        },
        "enter_id": {
            RESPONSE: "Введите id комнаты, или присоединитесь к случайной",
            # TRANSITIONS: [Tr(dst(""), )],
            # TRANSITIONS: [Tr(dst(""), )],
        },
    },
}

pipeline = Pipeline(
    mafia_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("global_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
