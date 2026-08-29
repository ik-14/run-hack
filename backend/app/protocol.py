"""Wire protocol between the phone client and the game server.

See DESIGN.md §4. Only the lobby subset of the protocol is implemented so far.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

MAX_NAME_LENGTH = 16
ROUND_MINUTE_CHOICES = (5, 10, 20)


class Create(BaseModel):
    type: Literal["create"]
    name: str

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return clean_name(value)


class Join(BaseModel):
    type: Literal["join"]
    room: str
    name: str

    @field_validator("room")
    @classmethod
    def _clean_room(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return clean_name(value)


class Config(BaseModel):
    type: Literal["config"]
    round_minutes: int


class Start(BaseModel):
    type: Literal["start"]


ClientMessage = Annotated[Create | Join | Config | Start, Field(discriminator="type")]

client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def clean_name(value: str) -> str:
    name = " ".join(value.split())[:MAX_NAME_LENGTH]
    if not name:
        raise ValueError("name must not be empty")
    return name


def parse_client_message(raw: str | bytes) -> ClientMessage:
    return client_message_adapter.validate_json(raw)
