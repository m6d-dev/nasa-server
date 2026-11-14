from functools import cached_property
from typing import Annotated
from urllib.parse import quote

from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

# a Postgres identifier: letters, digits, _ ; up to 63 bytes
ATPgName = Annotated[str, StringConstraints(min_length=1, max_length=63, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
ATHost = Annotated[str, StringConstraints(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.\-]+$")]


class DatabaseConfig(BaseSettings):
    """POSTGRES_* variables, as in the CRM. The same names feed the postgres
    container in docker-compose, so one .env serves both."""

    user: ATPgName = "vigil"
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)] = "vigil"
    db: ATPgName = "vigil"
    host: ATHost = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    driver: Annotated[str, StringConstraints(pattern=r"^asyncpg$")] = "asyncpg"

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        env_ignore_empty=True,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @cached_property
    def url(self) -> str:
        # quoted: a password with @ or / would otherwise break the URL
        return f"postgresql+{self.driver}://{quote(self.user)}:{quote(self.password, safe='')}@{self.host}:{self.port}/{self.db}"
