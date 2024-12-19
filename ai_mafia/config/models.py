from pydantic import BaseModel


class DBConfig(BaseModel):
    clear_previous: bool
    host: str
    port: int
    name: str

    @property
    def address(self):
        return f"mongodb://{self.host}:{self.port}"


class ChatskyConfig(BaseModel):
    host: str
    port: int


class AIMafiaConfig(BaseModel):
    db: DBConfig
    chatsky: ChatskyConfig
