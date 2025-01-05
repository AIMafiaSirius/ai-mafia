from bson.objectid import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from ai_mafia.types import PlayerState, RoomState


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


class PlayerModel(BaseModel):
    user_id: str | None

    role: str | None = None

    state: PlayerState = PlayerState.NOT_READY

    number: int | None = None

    ctx_id: int

    chat_id: int

    shoot_cnt: int = 0


class RoomModel(BaseModel):
    """Data model for storing info about room."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_id: ObjectId | None = Field(default=None, alias="_id", description="Unique identifier in mongo db")

    room_id: str
    """Usable room's id for users"""

    name: str
    """Name of this game room"""

    last_words: str | None = None

    room_state: RoomState = RoomState.CREATED

    list_players: list[PlayerModel] = []
    """List of user's tg id in the game room"""

    def change_player_state(self, user_db_id: str, state: PlayerState):
        for player in self.list_players:
            if player.user_id == user_db_id:
                player.state = state
                break
        else:
            msg = "Something's wrong. Player not found"
            raise ValueError(msg)

    def is_room_ready(self, n_players_to_wait: int):
        """
        Check whether there are 10 ready players in the room
        """
        ready_count = sum(player.state == PlayerState.READY for player in self.list_players)
        return ready_count == n_players_to_wait

    def get_player(self, user_db_id: str) -> PlayerModel | None:
        for player in self.list_players:
            if player.user_id == user_db_id:
                return player
        return None

    def get_cnt_black(self):
        cnt = 0
        for player in self.list_players:
            if player.state == PlayerState.ALIVE and player.role in ("мафия", "дон"):
                cnt += 1
        return cnt

    def kill(self) -> bool:
        shoot_cnt = self.get_cnt_black()
        flag = False
        for player in self.list_players:
            if player.shoot_cnt == shoot_cnt:
                player.state = PlayerState.PRE_DEAD
                flag = True
            player.shoot_cnt = 0
        return flag

    def get_pre_dead_player(self) -> PlayerModel | None:
        for player in self.list_players:
            if player.state == PlayerState.PRE_DEAD:
                return player
        return None
