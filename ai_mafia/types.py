from enum import Enum


class PlayerState(Enum):
    NOT_READY = "not_ready"
    READY = "ready"
    ALIVE = "alive"
    PRE_DEAD = "pre_dead"
    DEAD = "dead"


class RoomState(Enum):
    CREATED = "created"
    STARTED = "started"
    ENDED = "ended"


class PlayerRole(Enum):
    MAFIA = "mafia"
    DON = "don"
    COMMISSAR = "commissar"
    RED = "red"

    @classmethod
    def all_roles(cls) -> list["PlayerRole"]:
        return [cls.DON, cls.COMMISSAR] + [cls.MAFIA] * 2 + [cls.RED] * 6

    def is_black(self):
        return self.value in ["mafia", "don"]
