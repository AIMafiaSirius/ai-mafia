import chatsky.conditions as cnd
import chatsky.destinations as dst
from chatsky import RESPONSE, TRANSITIONS, Pipeline
from chatsky import Transition as Tr

from uuid import uuid1

map_id = {}

mafia_script = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))]
            # start node handles the initial handshake (command /start)
        },
        "greeting_node": {
            RESPONSE: "Привет! Нужна ли вам инструкция по игре?",
            TRANSITIONS: [Tr(dst=("game_start_node"), cnd=cnd.ExactMatch("Да"))],
            TRANSITIONS: [Tr(dst=("choose_room"), cnd=cnd.ExactMatch("Нет"))],
        },
        "instruction": {
            # RESPONSE: "...",
            TRANSITIONS: [Tr(dst=("choose_room"))],
        },
        "choose_room": {
            RESPONSE: "Создай комнату или присоединись к существующей",
            TRANSITIONS: [Tr(dst=("enter_id"), cnd=cnd.ExactMatch("Присоединиться"))],
            TRANSITIONS: [Tr(dst=("make_room"), cnd=cnd.ExactMatch("Создать"))],
        },
        "make_room": {
            RESPONSE: "Введите название для комнаты",
            # TRANSITIONS: [Tr(dst=())],
        },
        "enter_id": {
            RESPONSE: "Введите id комнаты, или присоединитесь к случайной",
            # TRANSITIONS: [Tr(dst(""), )],
            # TRANSITIONS: [Tr(dst(""), )],
        },
        
        "fallback_node": {
            RESPONSE: "К сожалению я не могу обработать такую команду, введите другую",
            # this transition is unconditional
        },
    },
    "ping_pong_flow": {
        "game_start_node": {
            RESPONSE: "Let's play ping-pong!",
            TRANSITIONS: [Tr(dst="response_node", cnd=cnd.ExactMatch("Ping!"))],
        },
        "response_node": {
            RESPONSE: "Pong!",
            TRANSITIONS: [Tr(dst=dst.Current(), cnd=cnd.ExactMatch("Ping!"))],
        },
    },
}

pipeline = Pipeline(
    mafia_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
