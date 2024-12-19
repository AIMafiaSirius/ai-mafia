import os

from chatsky import (
    PRE_RESPONSE,
    RESPONSE,
    TRANSITIONS,
    BaseCondition,
    BaseResponse,
    BaseProcessing,
    Context,
    Pipeline,
)
from chatsky import Transition as Tr
from chatsky.messengers.telegram import LongpollingInterface
from dotenv import load_dotenv

load_dotenv()


class ShootingResponse(BaseResponse):
    async def call(self, ctx: Context):
        role = ctx.misc["user_info"]
        if role in ("мафия", "дон"):
            return "Наступает ночь! Напишите номер игрока, в которого будете стрелять."
        return "Наступает ночь! Мафия выбирает, кого убить."


class CheckResponse(BaseResponse):
    async def call(self, ctx: Context):
        role = ctx.misc["user_info"]
        is_alive = ctx.misc["room_info"].is_alive[ctx["user_info"].number]

        if role == "комиссар" and is_alive:
            return "Вы - комиссар. Напишите номер игрока, которого хотите проверить\
                  (чёрный - мафия или дон, красный - мирный)."

        if role in ("мафия", "дон"):
            return "Вы - дон мафии. Напишите номер игрока, которого хотите проверить на комиссарство"

        return "Дон и комиссар делают проверки."


def get_role(ctx: Context) -> str:
    return ctx.misc["room_info"].players[ctx.misc["user_info"].number]


class IsCom(BaseCondition):
    async def call(self, ctx: Context) -> bool:
        return get_role(ctx) == "комиссар"


class IsDon(BaseCondition):
    async def call(self, ctx: Context) -> bool:
        return get_role(ctx) == "дон"


class ComsCheckResponse(BaseResponse):
    async def call(self, ctx: Context) -> str:
        request = ctx.last_request
        num = int(request.text)
        role = ctx.misc["room_info"].players[num].role

        color = role in ("мафия", "дон") if "чёрный" else "красный"
        return f"Этот игрок {color}"


class DonsCheckResponse(BaseResponse):
    async def call(self, ctx: Context) -> str:
        request = ctx.last_request
        num = int(request.text)
        role = ctx.misc["room_info"].players[num].role

        is_com = role == "комиссар" if "комиссар" else "не комиссар"
        return f"Этот игрок {is_com}"


def get_cnt_black(ctx: Context) -> int:
    return len(ctx.misc["room_info"].pos["black"])


class MafiaChoiceCheck(BaseProcessing):
    def call(self, ctx: Context):
        pass


night_script = {
    "shooting_phase": {
        RESPONSE: ShootingResponse,
        TRANSITIONS: [Tr("coms_check")],
    },
    "checks": {
        RESPONSE: CheckResponse,
        TRANSITIONS: [Tr("coms_check", cnd=IsCom), Tr("dons_check", cnd=IsDon)],
    },
    "coms_check": {
        RESPONSE: ComsCheckResponse,
        TRANSITIONS: [Tr("end_of_night")]
    },
    "dons_check": {
        RESPONSE: DonsCheckResponse,
        TRANSITIONS: [Tr("end_of_night")]
    },
    "end_of_night": {
        PRE_RESPONSE: ...
    }
}

interface = LongpollingInterface(token=os.environ["TG_TOKEN"])

pipeline = Pipeline(
    night_script,
    start_label=("shooting_phase"),
    fallback_label=("greeting_flow", "fallback_node"),
    messenger_interface=interface,
)

if __name__ == "__main__":
    pipeline.run()
