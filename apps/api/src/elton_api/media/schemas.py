"""Transport and validation values for protected product media."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class MediaDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    type: Literal["image", "video"]
    url: str
    alt_text: str
    position: int


class MediaUploadMetadata(BaseModel):
    """Validated non-file fields. The file is always read from the request stream."""

    model_config = ConfigDict(extra="forbid")

    alt_text: StrictStr = Field(default="", max_length=500)
    position: StrictInt = Field(default=0, ge=0, le=2147483647)

