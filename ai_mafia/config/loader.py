import importlib.resources as ires

import yaml

from .models import AIMafiaConfig


def load_config() -> AIMafiaConfig:
    """Load configuration settings for mongo db"""
    path = ires.files("ai_mafia.config").joinpath("config.yaml")
    with path.open() as file:
        return AIMafiaConfig(**yaml.safe_load(file))
