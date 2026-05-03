from datetime import datetime

from pydantic import BaseModel, field_validator


class CommentCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment cannot be empty")
        if len(v) > 500:
            raise ValueError("Comment must be 500 characters or less")
        return v


class CommentRead(BaseModel):
    id: str
    user_identifier: str
    content: str
    created_at: datetime
    display_name: str | None = None
    avatar_path: str | None = None

    model_config = {"from_attributes": True}


class ActivityRead(BaseModel):
    id: str
    user_identifier: str
    activity_type: str
    reference_id: str
    description: str | None
    like_count: int
    comment_count: int
    created_at: datetime
    current_user_liked: bool = False
    comments: list[CommentRead] = []
    display_name: str | None = None
    avatar_path: str | None = None

    model_config = {"from_attributes": True}


class ActivityList(BaseModel):
    items: list[ActivityRead]
    total: int
    limit: int
    offset: int
