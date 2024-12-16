import os
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

    from ai_mafia.db.models import UserModel

load_dotenv()

class InitSessionProcessing(BaseProcessing):
    """
    Add user tg id to database.

    This custom processor is a demo of database usage and saving to context.
    """

    async def call(self, ctx: Context):
        tg_info: tg.Update = ctx.last_request.original_message
        user_id = tg_info.effective_user.id
        print(f"{user_id=}")
        user_nickname = tg_info.effective_user.name
        user_info = find_user(user_id)
        if user_info is None:
            user_info = add_user(user_id, user_nickname)
        ctx.misc["user_info"] = user_info


class GreetingResponse(BaseResponse):
    """
    Greet and provide info about user
    """

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        print(user_info)
        return f"Hello, {user_info.tg_nickname}! You pinged me {user_info.ping_counter} times in the past."

class PongResponse(BaseResponse):
    """
    Make response as "Pong, @username!".

    This custom response is a demo of context and db usage. Beside just returning response string,
    this object retrieves user tg nickname and increments total pings number.
    """

    async def call(self, ctx: Context):
        user_info: UserModel = ctx.misc["user_info"]
        up_to_date_counter = increment_counter(user_info.db_id)
        user_info.ping_counter = up_to_date_counter
        return f"Pong, {user_info.tg_nickname}! Total counter is {user_info.ping_counter}"


ping_pong_script = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))],
            PRE_TRANSITION: {"init": InitSessionProcessing()}
        },
        "greeting_node": {
            RESPONSE: GreetingResponse(),
            TRANSITIONS: [Tr(dst=("ping_pong_flow", "game_start_node"), cnd=cnd.ExactMatch("Hello!"))],
        },
        "fallback_node": {
            RESPONSE: "That was against the rules",
            TRANSITIONS: [Tr(dst="greeting_node")],
        },
    },
    "ping_pong_flow": {
        "game_start_node": {
            RESPONSE: "Let's play ping-pong!",
            TRANSITIONS: [Tr(dst="response_node", cnd=cnd.ExactMatch("Ping!"))],
        },
        "response_node": {
            RESPONSE: PongResponse(),
            TRANSITIONS: [Tr(dst=dst.Current(), cnd=cnd.ExactMatch("Ping!"))],
        },
    },
}

interface = LongpollingInterface(token=os.environ["TG_TOKEN"])

pipeline = Pipeline(
    ping_pong_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
    messenger_interface=interface,
)

if __name__ == "__main__":
    pipeline.run()
