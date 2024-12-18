#WITHOUT SYNCHRONISING WITH OTHER PLAYERS!!!!
import os
from typing import TYPE_CHECKING

import chatsky.conditions as cnd
import chatsky.destinations as dst
from chatsky import (
    PRE_TRANSITION,
    RESPONSE,
    TRANSITIONS,
    BaseCondition,
    BaseProcessing,
    BaseResponse,
    Context,
    Pipeline,
)
from chatsky import Transition as Tr
from chatsky.messengers.telegram import LongpollingInterface
from dotenv import load_dotenv

from ai_mafia.db.routines import add_user, find_user, increment_counter

if TYPE_CHECKING:
    import telegram as tg

    from ai_mafia.db.models import UserModel

load_dotenv()

class InitSessionProcessing(BaseProcessing):
    """
    Add user tg id to database.

    This custom processor is a demo of database usage and saving to context.
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
        return f"Hello, {user_info.tg_nickname}!"

self_num = 3

checking_players = {1:1, 2:0, 3:3, 4:2, 5:2, 6:0, 7:0, 8:1, 9:0, 10:1}
players = checking_players
request = None
def check_votes():
    async def call(self, ctx: Context) -> bool:
        max_res = 0
        num_of_max = 0
        for player in players:
            if players[player] > max_res:
                max_res = players[player]
                num_of_max = 1
            elif players[player] == max_res:
                max_res += 1
        print(num_of_max)
        if num_of_max > 1:
            print("was the same")
            return False
        print("will exclude")
        return True

def get_person_to_exclude():
    max_res = 0
    ex = []
    for player in players:
        if players[player] > max_res:
            max_res = players[player]
            ex = [player]
        elif players[player] == max_res:
            ex.append(player)
    return ex

class get_vote(BaseCondition):
    async def call(self, ctx: Context) -> bool:
        request = ctx.last_request
        checking_players[int(request)] += 1
        print(f"you voted {request}")
        return True

voting_script = {
    "voting_flow":{
        "start_node":{
            TRANSITIONS: [Tr(dst="vote_node", cnd=cnd.ExactMatch("/start"))],
            PRE_TRANSITION: {"init": InitSessionProcessing()}
        },
        "fallback_node": {
            RESPONSE: "You`ve done something wrong",
            TRANSITIONS: [Tr(dst="start_node")],
        },
        "vote_node":{
            RESPONSE: "Choose person who you want to exclude",
            TRANSITIONS: [ Tr(dst='voted_node', cnd=get_vote())]
        },
        "voted_node":{
            RESPONSE: f"you`ve done your choice",
            TRANSITIONS: [Tr(dst="exclude_node", cnd = check_votes()), Tr(dst='second_vote_node', cnd = not check_votes)]
        },
        "second_vote_node":{
            RESPONSE: "chosen players have a minute to their speech",
            TRANSITIONS: [Tr(dst="end_node")]
        },
        "exclude_node":{
            RESPONSE: f"{get_person_to_exclude()} was excluded" if self_num not in get_person_to_exclude() else "You`ve been excluded",
            TRANSITIONS: [Tr(dst="end_node")]
        },
        "end_node":{
            RESPONSE: "This is the end",
            TRANSITIONS: [Tr(dst="start_node")]
        }

    }}

interface = LongpollingInterface(token=os.environ["TG_TOKEN"])

pipeline = Pipeline(
    voting_script,
    start_label=("voting_flow", "start_node"),
    fallback_label=("voting_flow", "fallback_node"),
    messenger_interface=interface,
    )
if __name__ == "__main__":
    pipeline.run()

