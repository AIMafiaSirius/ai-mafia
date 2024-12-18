from uuid import uuid4

from bson.objectid import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class UserModel(BaseModel):
    """Data model for storing info about user."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(default=None, alias="_id", description="Unique identifier in mongo db")

    tg_id: int
    """User's telegram id"""

    tg_nickname: str
    """User's telegram nickname"""

    room_id: ObjectId | None
    """Id of a room there user currently in"""

    win_counter: int = 0
    """Total number of wins from this user from all his sessions."""

    game_counter: int = 0
    """Total number of played games from this user from all his sessions."""


class Player:
    user_id: ObjectId | None

    role: str | None = None

    is_alive: bool = True

    def __init__(self, user: UserModel):
        self.user_id = user.db_id


class RoomModel(BaseModel):
    """Data model for storing info about room."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(default=None, alias="_id", description="Unique identifier in mongo db")

    room_id: uuid4
    """Usable room's id for users"""

    name: str
    """Name of this game room"""

    is_game_start: bool = False

    list_users: list
    """List of user's tg id in the game room"""
