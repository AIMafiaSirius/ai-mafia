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
from bson.objectid import ObjectId

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import Player, UserModel
load_dotenv()



class Player:
    user_num: int = -1

    role: str | None = None

    is_alive: bool = True


players = ["976818136", "976818136", "976818136", "976818136", "976818136", "976818136", "976818136", "976818136", 
           "976818136", "976818136"]
players_role = ["комиссар", "мафия", "мафия", "дон", "мирный", "мирный", "мирный", "мирный", "мирный", "мирный"]

gamers = {}

def mix(arr):
    for i in range(len(arr)):
        r = randint(0, i)
        arr[i], arr[r] = arr[r], arr[i]
    return arr

def get_role_for_all():
    for i in range(10):
        cur = Player()
        cur.is_alive = True
        cur.user_num = i
        cur.role = players_role[i]

        gamers[players[i]] = cur

mix(players)
mix(players_role)
get_role_for_all()

class GetCards(BaseResponse):
    async def call(self, ctx: Context):
        #players_info: UserModel = ctx.misc["user_info"]
        get_id = "976818136"
        return f"Игрок номер {gamers[get_id].user_num + 1} ваша карта: {gamers[get_id].role}"


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
