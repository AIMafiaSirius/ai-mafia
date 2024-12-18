import os
from random import randint
from typing import TYPE_CHECKING

import chatsky.conditions as cnd
import chatsky.destinations as dst
from chatsky import PRE_TRANSITION, RESPONSE, TRANSITIONS, BaseProcessing, BaseResponse, Context, Pipeline
from chatsky import Transition as Tr
from chatsky.messengers.telegram import LongpollingInterface
from dotenv import load_dotenv

from ai_mafia.db.routines import add_user, find_user, increment_counter

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import Player, UserModel

players = ["id1", "id2", "id3", "id4", "id5", "id6", "id7", "id8", "id9", "id10"]
players_role = ["комиссар", "мафия", "мафия", "дон", "мирный", "мирный", "мирный", "мирный", "мирный", "мирный"]

gamers = {}

def mix(arr):
    for i in range(len(arr)):
        r = randint(0, i)
        arr[i], arr[r] = arr[r], arr[i]
    return arr

def get_role_for_all():
    for i in range(10):
        gamers.append(Player)
        gamers[players[i]].user_id = i
        gamers[players[i]].role = players_role[i]
        gamers[players[i]].is_alive = True

mix(players)
mix(players_role)
get_role_for_all()

class GetCards(BaseResponse):
    async def call(self, ctx: Context):
        players_info: Player = ctx.misc["user_info"]
        get_id = players_info.tg_id
        return f"Игрок номер {gamers[get_id].number} ваша карта: {gamers[get_id].role}"


get_card_script = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst=("get_role_flow", "game_start_node"), cnd=cnd.ExactMatch("/start"))],
        },
        "fallback_node": {
            RESPONSE: "That was against the rules",
            TRANSITIONS: [Tr(dst="greeting_node")],
        },
    },
    "get_role_flow": {
        "game_start_node": {
            RESPONSE: "Сheck the card!",
            TRANSITIONS: [Tr(dst="response_node", cnd=cnd.ExactMatch("Сheck"))],
        },
        "response_node": {
            RESPONSE: GetCards(),
            # TRANSITIONS: [Tr(dst=dst.Current(), cnd=cnd.ExactMatch("Continue"))],
            # переход на ночь
        },
    },
}

interface = LongpollingInterface(token=os.environ["TG_TOKEN"])

pipeline = Pipeline(
    get_card_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
    messenger_interface=interface,
)

if __name__ == "__main__":
    pipeline.run()
