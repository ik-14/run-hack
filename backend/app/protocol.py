"""Wire protocol between the phone client and the game server.

See DESIGN.md §4. Only the lobby subset of the protocol is implemented so far.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

MAX_NAME_LENGTH = 16
ROUND_MINUTE_CHOICES = (5, 10, 20)

# Fixed palette so no two players end up with near-identical shades (DESIGN.md §4).
PALETTE = (
    "#84cc16",
    "#f97316",
    "#06b6d4",
    "#ec4899",
    "#a855f7",
    "#eab308",
    "#ef4444",
    "#22d3ee",
)


class Create(BaseModel):
    type: Literal["create"]
    name: str
    color: str | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        return clean_color(value)


class Join(BaseModel):
    type: Literal["join"]
    room: str
    name: str
    color: str | None = None

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        return clean_color(value)

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


class Bounds(BaseModel):
    """The play-area rectangle the host drags out on the map."""

    type: Literal["bounds"]
    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def _check_order(self) -> "Bounds":
        if self.north <= self.south or self.east <= self.west:
            raise ValueError("the play area must have a positive width and height")
        return self


class Start(BaseModel):
    type: Literal["start"]


ClientMessage = Annotated[Create | Join | Config | Bounds | Start, Field(discriminator="type")]

client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def clean_color(value: str | None) -> str | None:
    if value is None:
        return None
    color = value.strip().lower()
    if color not in PALETTE:
        raise ValueError("pick a colour from the palette")
    return color


def clean_name(value: str) -> str:
    name = " ".join(value.split())[:MAX_NAME_LENGTH]
    if not name:
        raise ValueError("name must not be empty")
    return name


def parse_client_message(raw: str | bytes) -> ClientMessage:
    return client_message_adapter.validate_json(raw)
