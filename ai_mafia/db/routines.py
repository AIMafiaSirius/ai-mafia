import random

from bson.objectid import ObjectId
from pymongo import MongoClient

from .models import RoomModel, UserModel
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


def add_game_room(name_room: str) -> RoomModel:
    """Add new game room and store info in database, return created room"""
    room = RoomModel(name=name_room)
    result = rooms_collection.insert_one(room.model_dump())
    room.db_id = result.inserted_id
    return room


def get_random_room() -> RoomModel | None:
    """
    If any game room open, randomly return one of them.
    Otherwise, return None.
    """
    list_room = list(rooms_collection.find({"room_state": "created"}))
    if len(list_room) == 0:
        return None
    room = random.choice(list_room)
    return RoomModel(**room)

# def insert_game_room(game_id, game_name, users):
#     game_room = {"game_id": game_id, "game_name": game_name, "users": users}
#     game_rooms_collection.insert_one(game_room)
