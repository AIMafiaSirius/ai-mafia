from typing import Literal
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

    win_counter: int = 0
    """Total number of wins from this user from all his sessions."""

    game_counter: int = 0
    """Total number of played games from this user from all his sessions."""


PlayerState = Literal["not_ready", "ready", "alive", "dead"]


class PlayerModel(BaseModel):
    user_id: str | None

    role: str | None = None

    state: PlayerState = "not_ready"


RoomState = Literal["created", "started", "ended"]


class RoomModel(BaseModel):
    """Data model for storing info about room."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(default=None, alias="_id", description="Unique identifier in mongo db")

    room_id: str = str(int(uuid4()))
    """Usable room's id for users"""

    name: str
    """Name of this game room"""

    room_state: RoomState = "created"

    list_users: list[PlayerModel] = []
    """List of user's tg id in the game room"""

    def change_player_state(self, user_db_id: ObjectId, state: PlayerState):
        for player in self.list_users:
            if player.user_id == str(user_db_id):
                player.state = state
                break
        else:
            msg = "Something's wrong. Player not found"
            raise ValueError(msg)

    def is_room_ready(self):
        """
        check whether there are 10 ready players in the room
        """
        ready_count = sum(player.state == "ready" for player in self.list_users)
        return ready_count == 10  # noqa: PLR2004
