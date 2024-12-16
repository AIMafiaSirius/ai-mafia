import random
from enum import Enum

import chatsky.conditions as cnd
from chatsky import PRE_TRANSITION, RESPONSE, TRANSITIONS, BaseProcessing, BaseResponse, Context, Pipeline
from chatsky import Transition as Tr


class Role(Enum):
    peaceful = "мирный"
    commissar = "комиссар"
    mafia = "мафия"
    don = "дон"


class AssignRoles(BaseProcessing):
    async def call(self, ctx: Context):
        # retrieve by room's id from database
        ctx.misc["players_id"] = [
            "id_1",
            "id_2",
            "id_3",
            "id_4",
            "id_5",
            "id_6",
            "id_7",
            "id_8",
            "id_9",
            "id_10",
        ]

        # retrieve roles from database if exist
        # else initialize
        ctx.misc["players_roles"] = {
            player_id: random.choice(list(Role)) for player_id in ctx.misc["players_id"]
        }


class RoleResponse(BaseResponse):
    async def call(self, ctx: Context):
        "Начало игры, раздача карт!"
        current_user_role: Role = ctx.misc["players_roles"]["id_8"] # should be `ctx.id`
        return current_user_role.value


mafia_get_role = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/get_role"))],
            PRE_TRANSITION: {"assign_roles": AssignRoles()},
        },
        "greeting_node": {
            RESPONSE: RoleResponse(),
        },
        "fallback_node": {
            RESPONSE: "That was against the rules",
            TRANSITIONS: [Tr(dst="greeting_node")],
            # не правильный текст
        },
    },
}

pipeline = Pipeline(
    mafia_get_role,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
