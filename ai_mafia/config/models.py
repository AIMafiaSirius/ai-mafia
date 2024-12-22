from pydantic import BaseModel


class DBConfig(BaseModel):
    clear_previous: bool
    host: str
    port: int
    name: str

    @property
    def address(self):
        return f"mongodb://{self.host}:{self.port}/"


class ChatskyConfig(BaseModel):
    host: str
    port: int

    @property
    def address(self):
        return f"http://{self.host}:{self.port}/"

    @property
    def chat_endpoint(self):
        return self.address + "chat"


class AIMafiaConfig(BaseModel):
    db: DBConfig
    chatsky: ChatskyConfig
