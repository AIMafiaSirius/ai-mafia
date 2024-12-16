from bson.objectid import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class UserModel(BaseModel):
    """Data model for storing info about user."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(
        default=None,
        alias="_id",
        description="Unique identifier in mongo db. User's telegram id"
    )

    tg_nickname: str
    """User's telegram nickname"""

    ping_counter: int = 0
    """Total number of pings from this user from all his sessions."""
