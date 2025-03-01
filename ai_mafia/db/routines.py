import random
from uuid import uuid4

from bson.objectid import ObjectId
from pymongo import MongoClient

from ai_mafia.types import PlayerRole, PlayerState, RoomState

from .models import PlayerModel, RoomModel, UserModel
from .setup import load_config

config = load_config().db

# Connect to the MongoDB server
client = MongoClient(host=config.host, port=config.port)

# Select the database
db = client.get_database(config.name)

# Select the collections
users_collection = db.get_collection("users")
rooms_collection = db.get_collection("game_rooms")


def find_user(tg_id: int) -> UserModel | None:
    """
    If info about this tg user is stored in our database,
    return it. Otherwise, return None.
    """
    result = users_collection.find_one({"tg_id": tg_id})
    if result is None:
        return None
    return UserModel(**result)


def add_user(tg_id: int, tg_nickname: str) -> UserModel:
    """Add info about user to database and return full info about him."""
    user = UserModel(tg_id=tg_id, tg_nickname=tg_nickname)
    result = users_collection.insert_one(user.model_dump())
    user.db_id = result.inserted_id
    return user


def get_tg_username(db_id: ObjectId) -> str:
    result = users_collection.find_one({"_id": db_id})
    return result["tg_nickname"]


def increment_counter(db_id: ObjectId) -> int:
    """Increment win counter for a given user by 1 and return resulting value."""
    users_collection.update_one({"_id": db_id}, {"$inc": {"win_counter": 1}})
    return get_counter(db_id)


def get_counter(db_id: ObjectId) -> int:
    """Find and return win counter for a given user."""
    result = users_collection.find_one({"_id": db_id})
    return result["win_counter"]


def find_game_room(room_id: str) -> RoomModel | None:
    """
    If info about this game room is stored in our database,
    return it. Otherwise, return None.
    """
    result = rooms_collection.find_one({"room_id": room_id})
    if result is None:
        return None
    return RoomModel(**result)


def add_room(name_room: str) -> RoomModel:
    """Add new game room and store info in database, return created room"""
    room = RoomModel(name=name_room, room_id=str(uuid4().hex))
    result = rooms_collection.insert_one(room.model_dump(mode="json"))
    room.db_id = result.inserted_id
    return room


def get_random_room() -> RoomModel | None:
    """
    If any game room open, randomly return one of them.
    Otherwise, return None.
    """
    list_room = list(rooms_collection.find({"room_state": RoomState.CREATED.value}))
    if len(list_room) == 0:
        return None
    room = random.choice(list_room)
    return RoomModel(**room)


def set_player_state(user_db_id: ObjectId, room_db_id: ObjectId, state: PlayerState) -> RoomModel:
    """Mark user as ready and return updated room model"""
    room = rooms_collection.find_one({"_id": room_db_id})
    if room is None:
        msg = "Something's wrong. Room not found"
        raise RuntimeError(msg)
    room_model = RoomModel(**room)
    room_model.change_player_state(user_db_id=str(user_db_id), state=state)
    list_players_dict = [player.model_dump(mode="json") for player in room_model.list_players]
    rooms_collection.update_one({"_id": room_db_id}, {"$set": {"list_players": list_players_dict}})
    return room_model


def show_rooms():
    for doc in rooms_collection.find():
        print(doc)


def is_room_ready(room_db_id: ObjectId):
    """
    Check whether there are 10 ready players in the room
    """
    # TODO async find_one
    room = rooms_collection.find_one({"_id": room_db_id})
    if room is None:
        msg = "Something's wrong. Room not found"
        raise RuntimeError(msg)
    room_model = RoomModel(**room)
    return room_model.is_room_ready()


def join_room(user_db_id: ObjectId, room_db_id: ObjectId, ctx_id: str, chat_id: int):
    room = rooms_collection.find_one({"_id": room_db_id})
    if room is None:
        msg = "Something's wrong. Room not found"
        raise RuntimeError(msg)
    lst_players: list = room["list_players"]
    lst_players.append(PlayerModel(user_id=str(user_db_id), ctx_id=ctx_id, chat_id=chat_id).model_dump(mode="json"))
    rooms_collection.update_one({"_id": room_db_id}, {"$set": {"list_players": lst_players}})


def exit_room(user_db_id: ObjectId, room_db_id: ObjectId):
    room = rooms_collection.find_one({"_id": room_db_id})
    if room is None:
        msg = "Something's wrong. Room not found"
        raise RuntimeError(msg)
    exit_id = str(user_db_id)
    lst_players: list = room["list_players"]
    for i in range(len(lst_players)):
        if lst_players[i]["user_id"] == exit_id:
            lst_players.pop(i)
            break
    else:
        msg = "Something's wrong. User not found in the room"
        raise ValueError(msg)
    rooms_collection.update_one({"_id": room_db_id}, {"$set": {"list_players": lst_players}})


def start_game(room_db_id: ObjectId):
    room = RoomModel(**rooms_collection.find_one({"_id": room_db_id}))

    roles = PlayerRole.all_roles()
    random.shuffle(roles)

    for i, player in enumerate(room.list_players):
        player.state = PlayerState.ALIVE
        player.role = roles[i]
        player.number = i + 1

    dumped_players_list = room.model_dump(mode="json")["list_players"]

    rooms_collection.update_one(
        {"_id": room_db_id}, {"$set": {"list_players": dumped_players_list, "room_state": RoomState.STARTED.value}}
    )


def shoot(room_db_id: ObjectId, player_number: int):
    room = RoomModel(**rooms_collection.find_one({"_id": room_db_id}))

    for player in room.list_players:
        if player.number == player_number:
            player.shoot_cnt += 1
            break

    dumped_players_list = room.model_dump(mode="json")["list_players"]

    rooms_collection.update_one({"_id": room_db_id}, {"$set": {"list_players": dumped_players_list}})


def murder(room_id: str) -> bool:
    room = find_game_room(room_id)
    res = room.kill()
    list_players_dict = [player.model_dump(mode="json") for player in room.list_players]
    rooms_collection.update_one({"room_id": room_id}, {"$set": {"list_players": list_players_dict}})
    return res


def update_last_words(room_id: str, msg: str):
    rooms_collection.update_one({"room_id": room_id}, {"$set": {"last_words": msg}})
