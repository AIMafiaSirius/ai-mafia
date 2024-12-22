from pydantic import BaseModel


class DBConfig(BaseModel):
    clear_previous: bool
    host: str
    port: int
    name: str

    @property
    def address(self):
        return f"mongodb://{self.host}:{self.port}/"


class EndpointConfig(BaseModel):
    host: str
    port: int

    @property
    def address(self):
        return f"http://{self.host}:{self.port}/"

    def make_endpoint(self, name: str):
        return self.address + name


class ChatskyConfig(EndpointConfig): ...


class SynchronizerConfig(EndpointConfig): ...



class AIMafiaConfig(BaseModel):
    db: DBConfig
    chatsky: ChatskyConfig
    sync: SynchronizerConfig
