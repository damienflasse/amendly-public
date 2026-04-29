"""
Tests for the word-level diff engine in app/utils/diff.py.

Coverage:
  compute_diff — pure function, no I/O, no DB
    - identical texts → all equal tokens
    - completely different texts → delete + insert
    - one word changed → delete old word + insert new word + surrounding equal
    - inserted words → equal + insert
    - deleted words → equal + delete
    - empty original → single insert token
    - empty proposed → single delete token
    - both empty → empty token list
    - multi-word phrases are joined with a single space
    - types are exactly "equal", "insert", or "delete"

  GET /api/…/amendments/{amendment_id}/diff endpoint
    - any member can fetch the diff → 200 with tokens list
    - non-member gets 404
    - unauthenticated gets 401/403
    - tokens cover the amendment texts
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app
from app.utils.diff import compute_diff

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Unit tests for compute_diff (pure function — no fixtures needed)
# ---------------------------------------------------------------------------


def test_identical_texts():
    """Identical strings produce a single equal token covering all words."""
    tokens = compute_diff("hello world", "hello world")
    assert len(tokens) == 1
    assert tokens[0]["type"] == "equal"
    assert tokens[0]["text"] == "hello world"


def test_completely_different():
    """Fully different texts produce a delete then an insert token."""
    tokens = compute_diff("foo bar", "baz qux")
    types = [t["type"] for t in tokens]
    # Must contain at least one delete and one insert; no equal
    assert "delete" in types
    assert "insert" in types
    assert "equal" not in types


def test_one_word_replaced():
    """Changing one word in a phrase gives delete + insert surrounded by equal."""
    tokens = compute_diff("The quick brown fox", "The quick red fox")
    types = [t["type"] for t in tokens]
    assert "equal" in types
    assert "delete" in types
    assert "insert" in types
    # "brown" should be in a delete token
    delete_texts = " ".join(t["text"] for t in tokens if t["type"] == "delete")
    assert "brown" in delete_texts
    # "red" should be in an insert token
    insert_texts = " ".join(t["text"] for t in tokens if t["type"] == "insert")
    assert "red" in insert_texts


def test_word_inserted():
    """Adding words at the end produces an insert token."""
    tokens = compute_diff("hello", "hello world")
    types = [t["type"] for t in tokens]
    assert "equal" in types
    assert "insert" in types
    assert "delete" not in types
    insert_texts = " ".join(t["text"] for t in tokens if t["type"] == "insert")
    assert "world" in insert_texts


def test_word_deleted():
    """Removing words from the end produces a delete token."""
    tokens = compute_diff("hello world", "hello")
    types = [t["type"] for t in tokens]
    assert "equal" in types
    assert "delete" in types
    assert "insert" not in types
    delete_texts = " ".join(t["text"] for t in tokens if t["type"] == "delete")
    assert "world" in delete_texts


def test_empty_original():
    """Empty original string → single insert token with all proposed words."""
    tokens = compute_diff("", "foo bar baz")
    assert len(tokens) == 1
    assert tokens[0]["type"] == "insert"
    assert tokens[0]["text"] == "foo bar baz"


def test_empty_proposed():
    """Empty proposed string → single delete token with all original words."""
    tokens = compute_diff("foo bar baz", "")
    assert len(tokens) == 1
    assert tokens[0]["type"] == "delete"
    assert tokens[0]["text"] == "foo bar baz"


def test_both_empty():
    """Both strings empty → empty token list."""
    tokens = compute_diff("", "")
    assert tokens == []


def test_token_types_valid():
    """Every token type is one of the three allowed values."""
    tokens = compute_diff("The board shall meet quarterly.", "The board shall meet monthly.")
    for t in tokens:
        assert t["type"] in ("equal", "insert", "delete")


def test_multi_word_groups_joined():
    """Consecutive equal words are grouped into a single token (joined by space)."""
    tokens = compute_diff("a b c d", "a b c d")
    assert len(tokens) == 1
    assert tokens[0]["text"] == "a b c d"


def test_whitespace_only_original_treated_as_empty():
    """Whitespace-only original is treated the same as empty."""
    tokens = compute_diff("   ", "hello")
    assert len(tokens) == 1
    assert tokens[0]["type"] == "insert"


def test_whitespace_only_proposed_treated_as_empty():
    """Whitespace-only proposed is treated the same as empty."""
    tokens = compute_diff("hello", "   ")
    assert len(tokens) == 1
    assert tokens[0]["type"] == "delete"


# ---------------------------------------------------------------------------
# Integration tests for GET …/amendments/{amendment_id}/diff
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def test_engine():
    """Shared in-memory SQLite engine for the integration tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Fresh AsyncSession per test, rolled back afterwards."""
    TestSession = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    """HTTP test client with get_db overridden to use the SQLite test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a user and return a JWT access token.

    Parameters:
        client: Test HTTP client.
        email: Email address for the new user.

    Returns:
        JWT access token string.
    """
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


async def _setup_amendment(
    client: AsyncClient,
    jwt: str,
    slug: str,
    original: str = "The board shall meet quarterly.",
    proposed: str = "The board shall meet monthly.",
) -> dict:
    """Create org, document, and amendment; return amendment dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Unique slug for the test organisation.
        original: original_text value for the amendment.
        proposed: proposed_text value for the amendment.

    Returns:
        Amendment response dict from the API.
    """
    await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    doc_res = await client.post(
        f"/api/organisations/{slug}/documents",
        json={"title": "Test Doc"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    doc_id = doc_res.json()["id"]
    amend_res = await client.post(
        f"/api/organisations/{slug}/documents/{doc_id}/amendments",
        json={"original_text": original, "proposed_text": proposed},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    return amend_res.json()


@pytest.mark.asyncio
async def test_diff_endpoint_returns_200(client):
    """A member can fetch the diff for an amendment — returns 200 with tokens."""
    jwt = await _register_and_login(client, "diff_ok@example.com")
    a = await _setup_amendment(client, jwt, "diff-ok-org")

    res = await client.get(
        f"/api/organisations/diff-ok-org/documents/{a['doc_id']}/amendments/{a['id']}/diff",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "tokens" in data
    assert isinstance(data["tokens"], list)
    assert len(data["tokens"]) > 0


@pytest.mark.asyncio
async def test_diff_endpoint_token_types(client):
    """All token types returned by the endpoint are valid."""
    jwt = await _register_and_login(client, "diff_types@example.com")
    a = await _setup_amendment(client, jwt, "diff-types-org")

    res = await client.get(
        f"/api/organisations/diff-types-org/documents/{a['doc_id']}/amendments/{a['id']}/diff",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    tokens = res.json()["tokens"]
    for t in tokens:
        assert t["type"] in ("equal", "insert", "delete")
        assert isinstance(t["text"], str)
        assert len(t["text"]) > 0


@pytest.mark.asyncio
async def test_diff_endpoint_reflects_texts(client):
    """Diff tokens cover both original and proposed words."""
    jwt = await _register_and_login(client, "diff_reflect@example.com")
    a = await _setup_amendment(
        client, jwt, "diff-reflect-org",
        original="foo bar baz",
        proposed="foo qux baz",
    )

    res = await client.get(
        f"/api/organisations/diff-reflect-org/documents/{a['doc_id']}/amendments/{a['id']}/diff",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    tokens = res.json()["tokens"]
    all_text = " ".join(t["text"] for t in tokens)
    assert "foo" in all_text
    assert "baz" in all_text
    delete_texts = " ".join(t["text"] for t in tokens if t["type"] == "delete")
    insert_texts = " ".join(t["text"] for t in tokens if t["type"] == "insert")
    assert "bar" in delete_texts
    assert "qux" in insert_texts


@pytest.mark.asyncio
async def test_diff_endpoint_unauthenticated(client):
    """Fetching diff without a token returns 401 or 403."""
    res = await client.get(
        "/api/organisations/some-org/documents/some-doc/amendments/some-id/diff"
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_diff_endpoint_non_member_returns_404(client):
    """A non-member gets 404 when fetching the diff."""
    jwt_owner = await _register_and_login(client, "diff_nm_owner@example.com")
    a = await _setup_amendment(client, jwt_owner, "diff-nm-org")

    jwt_outsider = await _register_and_login(client, "diff_nm_out@example.com")
    res = await client.get(
        f"/api/organisations/diff-nm-org/documents/{a['doc_id']}/amendments/{a['id']}/diff",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_diff_endpoint_amendment_not_found(client):
    """Fetching diff for a non-existent amendment returns 404."""
    jwt = await _register_and_login(client, "diff_nf@example.com")
    a = await _setup_amendment(client, jwt, "diff-nf-org")

    res = await client.get(
        f"/api/organisations/diff-nf-org/documents/{a['doc_id']}/amendments/00000000-0000-0000-0000-000000000000/diff",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404
