"""
Pydantic request/response schemas for the amendment comments API.

These are the data-transfer objects used by the
/api/organisations/{slug}/documents/{doc_id}/amendments/{aid}/comments routes.
"""

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CommentCreate(BaseModel):
    """Body for POST …/comments — post a new comment.

    Attributes:
        body: Plain-text comment body (1–2000 characters).
    """

    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        """Comment body must be non-empty and at most 2 000 characters."""
        v = v.strip()
        if not v:
            raise ValueError("body must not be empty")
        if len(v) > 2000:
            raise ValueError("body must be at most 2000 characters")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CommentResponse(BaseModel):
    """Comment fields returned by the API.

    Attributes:
        id: UUID of the comment.
        amendment_id: UUID of the parent amendment.
        author_id: UUID of the author (None if user has been deleted).
        author_name: Display name of the author at time of fetch.
        author_email: Email address of the author at time of fetch.
        body: Plain-text comment body.
        created_at: ISO-8601 UTC timestamp.
    """

    id: str
    amendment_id: str
    author_id: str | None
    author_name: str | None = None
    author_email: str | None = None
    body: str
    created_at: str

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    """Ordered list of comments for an amendment.

    Attributes:
        items: Comments ordered oldest-first.
        total: Total number of comments.
    """

    items: list[CommentResponse]
    total: int

    model_config = {"from_attributes": True}
