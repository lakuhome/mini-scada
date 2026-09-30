from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Quality = Literal["GOOD", "BAD"]
CommandStatus = Literal["ok", "accepted"]


class TagResponse(BaseModel):
    id: str
    value: Any
    timestamp: float
    quality: Quality


class TagsResponse(BaseModel):
    count: int
    tags: list[TagResponse]


class HistoryResponse(BaseModel):
    tag_id: str
    count: int
    history: list[TagResponse]


class WriteRegisterRequest(BaseModel):
    register_address: int = Field(
        alias="register",
        ge=0,
        le=65535,
        description="Modbus holding register address",
    )

    value: int = Field(
        ge=0,
        le=65535,
        description="Unsigned 16-bit register value",
    )

    model_config = {
        "populate_by_name": True,
    }


class CommandResponse(BaseModel):
    status: CommandStatus
    command: str
    register_address: int = Field(alias="register")
    value: int

    model_config = {
        "populate_by_name": True,
    }