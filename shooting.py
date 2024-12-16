import chatsky.conditions as cnd
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


class CheckRoleProcessing(BaseProcessing):
    async def call(self, ctx: Context):
        # retrieve from database info about room
        # extract info about user's role
        role = ...

        ctx.misc["user_role"] = role


def is_black(role: str) -> bool: ...


class IsBlackCondition(BaseCondition):
    async def call(self, ctx: Context):
        return is_black(ctx.misc["user_role"])


class GreetingResponse(BaseResponse):
    async def call(self, ctx: Context):
        role = ctx.misc["user_role"]
        if is_black(role):
            return "Сейчас ночь, вы чейрный, стреляйте. Напишите номер игрока."
        return "Сейчас ночь, вы красный, спите. Мафия сейчас стреляет."


ping_pong_script = {
    "flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))],
            PRE_TRANSITION: {"check_role": CheckRoleProcessing()},
        },
        "greeting_node": {
            RESPONSE: GreetingResponse(),
            TRANSITIONS: [
                Tr(dst="shooting_node", cnd=cnd.All(cnd.Regexp(r"\d"), IsBlackCondition())),
                Tr(dst="waiting_node", cnd=cnd.Negation(IsBlackCondition())),
            ],
        },
    },
}

pipeline = Pipeline(
    ping_pong_script,
    start_label=("flow", "start_node"),
    fallback_label=("flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
