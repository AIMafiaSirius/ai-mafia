import importlib.resources as ires

import yaml
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.database import Database


def create_database(client: MongoClient, db_name: str = "mafia_database"):
    """
    Create database with collections for storing info about users and game rooms.
    """
    db = client.get_database(db_name)

    db.create_collection("users")
    db.create_collection("game_rooms")

    print("Database and collections created successfully.")

    return db


def define_schema(db: Database):
    """
    This will ensure that only valid records are stored in a database.

    Read more on schema validation on mongodb here https://earthly.dev/blog/pymongo-advanced/#schema-validation
    """
    users_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["name"],
            "properties": {
                "name": {"bsonType": "string", "description": "must be a string and is required"},
            },
        }
    }

    game_rooms_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["game_name", "users"],
            "properties": {
                "game_name": {"bsonType": "string", "description": "must be a string and is required"},
                "users": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["user_id", "game_role", "user_state"],
                        "properties": {
                            "user_id": {"bsonType": "string", "description": "must be a string and is required"},
                            "game_role": {"bsonType": "string", "description": "must be a string and is required"},
                            "user_state": {"bsonType": "string", "description": "must be a string and is required"},
                        },
                    },
                },
            },
        }
    }

    db.command("collMod", "users", validator=users_validator)
    db.command("collMod", "game_rooms", validator=game_rooms_validator)

    print("Schema defined successfully.")


class DBConfig(BaseModel):
    clear_previous: bool
    address: str
    db_name: str


def load_config() -> DBConfig:
    """Load configuration settings for mongo db"""
    path = ires.files("ai_mafia.db").joinpath("config.yaml")
    with path.open() as file:
        return DBConfig(**yaml.safe_load(file))


def main():
    cfg = load_config()
    client = MongoClient(cfg.address)

    if cfg.clear_previous:
        client.drop_database(cfg.db_name)

    create_database(client, db_name=cfg.db_name)