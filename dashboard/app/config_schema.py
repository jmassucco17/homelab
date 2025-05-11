import pathlib

import pydantic
import yaml

QUERIES_CONFIG_PATH = pathlib.Path('app/queries.yaml')


class QueryConfig(pydantic.BaseModel):
    """Represents the top-level YAML config file"""

    queries: list['Query']


class Query(pydantic.BaseModel):
    """Represents an individual query configuration"""

    name: str
    label: str
    query: str
    unit: str
    types: list[str] = pydantic.Field(default_factory=lambda: ['widget'])


def load_queries_config(path: pathlib.Path = QUERIES_CONFIG_PATH) -> QueryConfig:
    """Load YAML into pydantic schema"""
    with path.open() as f:
        config = yaml.safe_load(f)
    return QueryConfig.model_validate(config)
