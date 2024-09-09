import asyncio
from typing import Self
from urllib.parse import urlparse

import pytest
from mock import patch
from pydantic import BaseModel
from testcontainers.postgres import PostgresContainer
from tortoise import Tortoise


class DatabaseConfig(BaseModel):
    host: str | None = None
    port: int = 5432
    username: str | None = None
    password: str | None = None
    name: str | None = None

    @property
    def connection_string(self) -> str:
        return f"postgres://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"

    @classmethod
    def from_connection_string(cls, connection_string: str) -> Self:
        result = urlparse(connection_string)
        if "postgres" not in result.scheme:
            raise ValueError(f"Not valid URL schema: {result.scheme}")

        return cls(
            name=result.path[1:],
            username=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
        )


TORTOISE_CONFIG = {
    "connections": {"default": None},
    "apps": {
        "default": {
            "models": ["tests.models"],
            "default_connection": "default",
        },
    },
    "use_tz": True,
    "timezone": "UTC",
}


def get_postgres_container() -> tuple[PostgresContainer | None, DatabaseConfig]:
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    db_config = DatabaseConfig.from_connection_string(container.get_connection_url())
    return (container, db_config)


@pytest.fixture(scope="session", autouse=True)
def initialize_tests(request, event_loop):
    postgres_container, db_config = get_postgres_container()

    test_config = TORTOISE_CONFIG.copy()
    test_config["connections"]["default"] = db_config.connection_string
    with patch("tortoise.connection.ConnectionHandler._get_db_info") as dbi:
        # Initialize the database
        dbi.return_value = db_config.connection_string
        event_loop.run_until_complete(Tortoise.init(config=test_config))
        event_loop.run_until_complete(Tortoise.generate_schemas(safe=False))
        Tortoise.apps = {}

        yield

    def custom_finalizer():
        if postgres_container:
            postgres_container.stop(delete_volume=True, force=True)

    request.addfinalizer(custom_finalizer)


@pytest.fixture(scope="session")
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    # TODO: find an other solution since replacing the event loop is deprecated
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
