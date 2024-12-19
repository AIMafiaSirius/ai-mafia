from bson.objectid import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class UserModel(BaseModel):
    """Data model for storing info about user."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(default=None, alias="_id", description="Unique identifier in mongo db")

    room_id: ObjectId | None

    tg_id: int
    """User's telegram id"""

    number: int | None
    """Number of the player in the room"""

    tg_nickname: str
    """User's telegram nickname"""

    ping_counter: int = 0
    """Total number of pings from this user from all his sessions."""


class Player:
    user_id: ObjectId

    role: str | None = None

    is_alive: bool = True

    pos: dict

    def __init__(self, user: UserModel):
        self.user_id = user.db_id


class RoomModel(BaseModel):
    """Data model for storing info about room."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(default=None, alias="_id", description="Unique idenrifier in mongo db")

    players: list

    game_started: bool
