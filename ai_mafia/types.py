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
