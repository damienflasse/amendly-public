"""
Pydantic request/response schemas for the documents API.

These are the data-transfer objects used by the
/api/organisations/{slug}/documents routes.
They are separate from the SQLAlchemy ORM models in app/models/.
"""

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


def _validate_required_title(value: str) -> str:
    """
    Normalize and validate a required document title.

    Parameters:
        value: Raw title string received from the client.

    Returns:
        Trimmed title string.

    Raises:
        ValueError: If the title is empty or exceeds 500 characters.
    """
    value = value.strip()
    if not value:
        raise ValueError("title must not be empty")
    if len(value) > 500:
        raise ValueError("title must be 500 characters or fewer")
    return value


def _validate_optional_title(value: str | None) -> str | None:
    """
    Normalize and validate an optional document title.

    Parameters:
        value: Optional raw title string received from the client.

    Returns:
        Trimmed title string, or None when omitted.

    Raises:
        ValueError: If a provided title is empty or exceeds 500 characters.
    """
    if value is None:
        return None
    return _validate_required_title(value)


class DocumentCreate(BaseModel):
    """Body for POST /api/organisations/{slug}/documents — create a document."""

    title: str
    # 5 MB cap to prevent DoS by oversized payloads
    body: str | None = Field(None, max_length=5_000_000)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Ensure title is non-empty after stripping whitespace."""
        return _validate_required_title(v)


class DocumentUpdate(BaseModel):
    """Body for PUT /api/organisations/{slug}/documents/{doc_id} — update a document."""

    title: str | None = None
    # 5 MB cap to prevent DoS by oversized payloads
    body: str | None = Field(None, max_length=5_000_000)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        """Ensure title, if provided, is non-empty after stripping whitespace."""
        return _validate_optional_title(v)


class DocumentStatusUpdate(BaseModel):
    """Body for PUT /api/organisations/{slug}/documents/{doc_id}/status — change lifecycle stage."""

    status: str  # "draft" | "open" | "closed"

    @field_validator("status")
    @classmethod
    def status_is_valid(cls, v: str) -> str:
        """Only draft, open, or closed are valid document statuses."""
        v = v.strip().lower()
        if v not in ("draft", "open", "closed"):
            raise ValueError("status must be 'draft', 'open', or 'closed'")
        return v


class SectionUpdate(BaseModel):
    """Body for PATCH /api/organisations/{slug}/documents/{doc_id}/sections.

    Allows updating section headings (h2/h3) in a document's body HTML
    when the document is in draft or closed status. The caller submits
    the full updated HTML body and may also update the title in the same
    request so closed-document edits stay atomic.
    """

    title: str | None = None
    # 5 MB cap mirrors the full-body update limit
    body: str = Field(..., max_length=5_000_000)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        """Ensure title, if provided, is non-empty after stripping whitespace."""
        return _validate_optional_title(v)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    """Document fields returned by the API."""

    id: str
    org_id: str
    title: str
    body: str | None
    status: str
    created_at: str  # ISO-8601 string — serialised in the service layer
    pending_count: int = 0  # number of pending amendments — included in list responses
    # Contributor public link fields (None when no token has been generated)
    contributor_token: str | None = None
    contributor_token_created_at: str | None = None  # ISO-8601 string or None
    contributor_token_expires_at: str | None = None  # ISO-8601 string or None
    contributor_link_status: str = "revoked"  # "active" | "expired" | "revoked"

    model_config = {"from_attributes": True}


class ContributorTokenResponse(BaseModel):
    """Response for POST/DELETE …/contributor-token.

    Attributes:
        token: The new contributor token (64-char hex), or None after revocation.
        created_at: ISO-8601 timestamp of token generation, or None after revocation.
        url: Full contribution URL ready to share, or None after revocation.
    """

    token: str | None
    created_at: str | None
    expires_at: str | None
    url: str | None
    status: str


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int

    model_config = {"from_attributes": True}


class ConsolidatedResponse(BaseModel):
    """
    Consolidated document body returned by GET …/consolidated.

    Represents the document body after all accepted amendments have been
    applied in chronological order.
    """

    title: str
    body_with_amendments_applied: str
    amendments_applied: int  # count of accepted amendments that were successfully applied

    model_config = {"from_attributes": True}


class DiffToken(BaseModel):
    """A single word-level diff token used in review responses.

    Attributes:
        text: The word or phrase represented by this token.
        type: One of 'equal', 'insert', or 'delete'.
    """

    text: str
    type: str  # "equal" | "insert" | "delete"

    model_config = {"from_attributes": True}


class ReviewAmendmentItem(BaseModel):
    """One accepted amendment included in the review payload.

    Attributes:
        id: Amendment UUID.
        section: Optional section label (e.g. 'Article 3').
        original_text: The passage that was replaced (None for general_comment).
        proposed_text: The replacement text (None for general_comment).
        justification: Author's explanation (may be None).
        author_name: Display name of the submitting user.
        created_at: ISO-8601 submission timestamp.
        diff_tokens: Word-level diff tokens for text_change amendments.
                     Empty list for general_comment amendments.
    """

    id: str
    section: str | None
    original_text: str | None
    proposed_text: str | None
    justification: str | None
    author_name: str
    created_at: str
    diff_tokens: list[DiffToken]

    model_config = {"from_attributes": True}


class ReviewResponse(BaseModel):
    """Full review payload returned by GET …/documents/{id}/review.

    Contains everything an owner/admin needs to verify the document before
    exporting: original body, consolidated body, a full-document diff, counts
    of amendments by status, and per-amendment detail for all accepted items.

    Attributes:
        title: Document title.
        original_body: The document body as originally written.
        consolidated_body: The document body after all accepted amendments
            have been applied in chronological order.
        full_diff_tokens: Word-level diff between original_body and
            consolidated_body — powers the inline review render.
        count_accepted: Number of accepted amendments.
        count_pending: Number of pending (not yet decided) amendments.
        count_rejected: Number of rejected amendments.
        count_withdrawn: Number of withdrawn amendments.
        accepted_amendments: Ordered list (oldest first) of accepted
            amendments with their per-amendment diff tokens.
    """

    title: str
    original_body: str
    consolidated_body: str
    full_diff_tokens: list[DiffToken]
    count_accepted: int
    count_pending: int
    count_rejected: int
    count_withdrawn: int
    accepted_amendments: list[ReviewAmendmentItem]

    model_config = {"from_attributes": True}
