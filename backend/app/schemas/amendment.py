"""
Pydantic request/response schemas for the amendments API.

These are the data-transfer objects used by the
/api/organisations/{slug}/documents/{doc_id}/amendments routes.
They are separate from the SQLAlchemy ORM models in app/models/.
"""

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AmendmentCreate(BaseModel):
    """Body for POST …/amendments — submit a new amendment.

    For amendment_type='text_change' (default):
        original_text and proposed_text are required.
    For amendment_type='general_comment':
        original_text and proposed_text are ignored / should be omitted.
        justification is required (it carries the comment body).
    """

    amendment_type: str = "text_change"
    section: str | None = None
    original_text: str | None = None
    proposed_text: str | None = None
    justification: str | None = None

    @field_validator("amendment_type")
    @classmethod
    def type_is_valid(cls, v: str) -> str:
        """Only 'text_change' or 'general_comment' are valid amendment types."""
        v = v.strip().lower()
        if v not in ("text_change", "general_comment"):
            raise ValueError("amendment_type must be 'text_change' or 'general_comment'")
        return v

    @model_validator(mode="after")
    def validate_type_fields(self) -> "AmendmentCreate":
        """
        Enforce field requirements that depend on amendment_type:
          - text_change: original_text and proposed_text must be non-empty.
          - general_comment: justification must be non-empty (serves as the comment body).
        """
        if self.amendment_type == "text_change":
            if not self.original_text or not self.original_text.strip():
                raise ValueError("original_text is required for text_change amendments")
            if not self.proposed_text or not self.proposed_text.strip():
                raise ValueError("proposed_text is required for text_change amendments")
            self.original_text = self.original_text.strip()
            self.proposed_text = self.proposed_text.strip()
        elif self.amendment_type == "general_comment":
            if not self.justification or not self.justification.strip():
                raise ValueError(
                    "justification (comment body) is required for general_comment amendments"
                )
            self.justification = self.justification.strip()
        return self


class AmendmentStatusUpdate(BaseModel):
    """Body for PUT …/amendments/{amendment_id}/status — accept or reject.

    decision_reason is optional — a plain-text explanation of the decision
    that will be stored on the amendment and shown to the author.
    """

    status: str           # "accepted" | "rejected"
    decision_reason: str | None = None

    @field_validator("status")
    @classmethod
    def status_is_valid(cls, v: str) -> str:
        """Only 'accepted' or 'rejected' are valid status transitions."""
        v = v.strip().lower()
        if v not in ("accepted", "rejected"):
            raise ValueError("status must be 'accepted' or 'rejected'")
        return v


class BulkAmendmentStatusUpdate(BaseModel):
    """Body for PATCH …/amendments/bulk-status — accept or reject multiple amendments.

    amendment_ids must be a non-empty list of UUIDs belonging to the same document.
    Only pending amendments are updated; others are silently skipped.
    decision_reason is optional and applied to all updated amendments.
    """

    amendment_ids: list[str]
    status: str           # "accepted" | "rejected"
    decision_reason: str | None = None

    @field_validator("status")
    @classmethod
    def status_is_valid(cls, v: str) -> str:
        """Only 'accepted' or 'rejected' are valid status transitions."""
        v = v.strip().lower()
        if v not in ("accepted", "rejected"):
            raise ValueError("status must be 'accepted' or 'rejected'")
        return v

    @field_validator("amendment_ids")
    @classmethod
    def ids_not_empty(cls, v: list[str]) -> list[str]:
        """amendment_ids must contain at least one entry."""
        if not v:
            raise ValueError("amendment_ids must not be empty")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ContributorAmendmentCreate(BaseModel):
    """Body for POST /api/contribute/{token} — anonymous contributor amendment.

    Extends the standard amendment fields with contributor identity fields.
    contributor_name is required; contributor_email is optional; the public
    Turnstile token is included when bot protection is enabled.
    """

    amendment_type: str = "text_change"
    section: str | None = None
    original_text: str | None = None
    proposed_text: str | None = None
    justification: str | None = None
    contributor_name: str
    contributor_email: str | None = None
    cf_turnstile_token: str | None = None

    @field_validator("amendment_type")
    @classmethod
    def type_is_valid(cls, v: str) -> str:
        """Only 'text_change' or 'general_comment' are valid amendment types."""
        v = v.strip().lower()
        if v not in ("text_change", "general_comment"):
            raise ValueError("amendment_type must be 'text_change' or 'general_comment'")
        return v

    @field_validator("contributor_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """contributor_name must be non-empty and at most 100 characters."""
        v = v.strip()
        if not v:
            raise ValueError("contributor_name is required")
        if len(v) > 100:
            raise ValueError("contributor_name must be 100 characters or fewer")
        return v

    @field_validator("contributor_email")
    @classmethod
    def email_max_length(cls, v: str | None) -> str | None:
        """contributor_email must be at most 254 characters if provided."""
        if v is not None:
            v = v.strip()
            if len(v) > 254:
                raise ValueError("contributor_email must be 254 characters or fewer")
            if not v:
                return None
        return v

    @field_validator("cf_turnstile_token")
    @classmethod
    def normalise_turnstile_token(cls, v: str | None) -> str | None:
        """Trim the Turnstile token and collapse blank values to None."""
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ContributorAmendmentCreate":
        """Enforce field requirements that depend on amendment_type."""
        if self.amendment_type == "text_change":
            if not self.original_text or not self.original_text.strip():
                raise ValueError("original_text is required for text_change amendments")
            if not self.proposed_text or not self.proposed_text.strip():
                raise ValueError("proposed_text is required for text_change amendments")
            self.original_text = self.original_text.strip()
            self.proposed_text = self.proposed_text.strip()
        elif self.amendment_type == "general_comment":
            if not self.justification or not self.justification.strip():
                raise ValueError(
                    "justification (comment body) is required for general_comment amendments"
                )
            self.justification = self.justification.strip()
        return self


class AmendmentResponse(BaseModel):
    """Amendment fields returned by the API."""

    id: str
    doc_id: str
    amendment_type: str   # text_change | general_comment
    section: str | None
    original_text: str | None
    proposed_text: str | None
    justification: str | None
    decision_reason: str | None
    status: str           # pending | accepted | rejected | withdrawn
    author_id: str | None
    author_name: str | None = None   # Display name of the amendment author
    author_email: str | None = None  # Email of the amendment author
    # Anonymous contributor fields (populated for public-link submissions)
    contributor_name: str | None = None
    contributor_email: str | None = None
    created_at: str       # ISO-8601 string — serialised in the service layer
    # Reaction counts (team/organisation plan only; 0 for solo)
    support_count: int = 0
    oppose_count: int = 0
    user_reaction: str | None = None  # "support" | "oppose" | None
    # Comment thread count — always available regardless of plan
    comment_count: int = 0

    model_config = {"from_attributes": True}


class ReactRequest(BaseModel):
    """Body for POST …/amendments/{id}/react.

    Posting the same type a second time cancels the reaction (toggle).
    Posting the opposite type replaces the previous reaction.
    """

    type: str  # "support" | "oppose"

    @field_validator("type")
    @classmethod
    def type_is_valid(cls, v: str) -> str:
        """Only 'support' or 'oppose' are valid reaction types."""
        v = v.strip().lower()
        if v not in ("support", "oppose"):
            raise ValueError("type must be 'support' or 'oppose'")
        return v


class AmendmentListResponse(BaseModel):
    """Paginated list of amendments."""

    items: list[AmendmentResponse]
    total: int
    page: int
    page_size: int

    model_config = {"from_attributes": True}


class ReactionSummaryResponse(BaseModel):
    """Aggregated reaction counts across all pending amendments for a document.

    Attributes:
        total_pending: Number of pending amendments on the document.
        support_count: Total support reactions across all pending amendments.
        oppose_count: Total oppose reactions across all pending amendments.
    """

    total_pending: int
    support_count: int
    oppose_count: int
