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


    number: int = None
    """"user number"""

class Player:
    user_id: ObjectId

    role: str | None = None

    is_alive: bool = True

    def __init__(self, user: UserModel):
        self.user_id = user.db_id