"""
Document endpoint tests — covers /api/organisations/{slug}/documents/* routes.

Uses the same in-memory SQLite + ASGI fixture pattern as test_organisations.py.
Each test gets a fresh HTTP client backed by a rolled-back DB session.

Coverage:
  POST   /api/organisations/{slug}/documents           — create
  GET    /api/organisations/{slug}/documents           — list (paginated)
  GET    /api/organisations/{slug}/documents/{doc_id}  — fetch one
  PUT    /api/organisations/{slug}/documents/{doc_id}  — update
  Access control: unauthenticated, non-member, member (read-only), owner/admin
"""

import pytest
from fpdf import FPDF
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app
from app.models.organisation import Organisation, OrgPlan

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def test_engine():
    """Create an async SQLite engine shared across all tests in the session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Yield a fresh AsyncSession for each test, rolling back after."""
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

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """
    Register a new user via magic link and return the JWT access token.

    Parameters:
        client: Test HTTP client.
        email: Email address for the test user.

    Returns:
        JWT access token string.
    """
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """
    Create an organisation and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Unique slug for the organisation.

    Returns:
        Organisation response dict from the API.
    """
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _create_doc(client: AsyncClient, jwt: str, slug: str, title: str = "Test Doc") -> dict:
    """
    Create a document and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Organisation slug.
        title: Document title.

    Returns:
        Document response dict from the API.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents",
        json={"title": title},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _upgrade_to_pro(slug: str) -> None:
    """
    Directly upgrade an organisation to the Pro plan in the test DB.

    Required for tests that create more than FREE_TIER_DOCUMENT_LIMIT (3) documents,
    since the free tier is now enforced at the service layer.

    Parameters:
        slug: URL slug of the organisation to upgrade.
    """
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == slug)
        )
        org = result.scalar_one()
        org.plan = OrgPlan.team
        await session.flush()
        break


# ---------------------------------------------------------------------------
# POST /api/organisations/{slug}/documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_document_success(client):
    """Owner can create a document — returns 201 with correct fields."""
    jwt = await _register_and_login(client, "docowner@example.com")
    await _create_org(client, jwt, "doc-create-org")

    res = await client.post(
        "/api/organisations/doc-create-org/documents",
        json={"title": "My First Document", "body": "Hello world"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "My First Document"
    assert data["body"] == "Hello world"
    assert data["status"] == "draft"
    assert "id" in data
    assert "created_at" in data
    assert "org_id" in data


@pytest.mark.asyncio
async def test_create_document_title_only(client):
    """Creating a document without a body is allowed (body is optional)."""
    jwt = await _register_and_login(client, "titonly@example.com")
    await _create_org(client, jwt, "title-only-org")

    res = await client.post(
        "/api/organisations/title-only-org/documents",
        json={"title": "Title Only"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    assert res.json()["body"] is None


@pytest.mark.asyncio
async def test_create_document_unauthenticated(client):
    """Creating a document without a token returns 401 or 403."""
    res = await client.post(
        "/api/organisations/some-org/documents",
        json={"title": "Ghost Doc"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_document_non_member_returns_404(client):
    """A user who is not a member of an org gets 404 when creating a document."""
    jwt_owner = await _register_and_login(client, "cdowner@example.com")
    await _create_org(client, jwt_owner, "cd-owner-org")

    jwt_outsider = await _register_and_login(client, "cdoutsider@example.com")
    res = await client.post(
        "/api/organisations/cd-owner-org/documents",
        json={"title": "Sneaky Doc"},
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_extract_pdf_returns_html(client):
    """PDF extraction returns structured HTML and infers a document title."""
    jwt = await _register_and_login(client, "pdfimport@example.com")
    await _create_org(client, jwt, "pdf-import-org")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "Board Resolution 2025\n\n"
        "This resolution approves the annual budget and confirms the vote."
    )
    pdf_bytes = bytes(pdf.output())

    res = await client.post(
        "/api/organisations/pdf-import-org/documents/extract-pdf",
        files={"file": ("agenda.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Board Resolution 2025"
    assert "<p>This resolution approves the annual budget and confirms the vote.</p>" in data["html"]
    assert "Board Resolution 2025" not in data["html"]
    assert data["char_count"] >= len(
        "Board Resolution 2025This resolution approves the annual budget and confirms the vote."
    )


@pytest.mark.asyncio
async def test_extract_pdf_infers_title_from_first_line_of_opening_block(client):
    """PDF extraction keeps the first line as title even without a blank line after it."""
    jwt = await _register_and_login(client, "pdfimport-inline@example.com")
    await _create_org(client, jwt, "pdf-inline-title-org")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "Board Resolution 2025\n"
        "This resolution approves the annual budget and confirms the vote.",
    )
    pdf_bytes = bytes(pdf.output())

    res = await client.post(
        "/api/organisations/pdf-inline-title-org/documents/extract-pdf",
        files={"file": ("agenda.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Board Resolution 2025"
    assert "<p>This resolution approves the annual budget and confirms the vote.</p>" in data["html"]
    assert "Board Resolution 2025 This resolution approves the annual budget and confirms the vote." not in data["html"]


@pytest.mark.asyncio
async def test_review_diff_uses_readable_text_not_html_tags(client):
    """Review diff should show readable content rather than raw HTML tags."""
    jwt = await _register_and_login(client, "review-html@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}
    await _create_org(client, jwt, "review-html-org")

    doc_res = await client.post(
        "/api/organisations/review-html-org/documents",
        json={
            "title": "Review Doc",
            "body": "<h2>Scope</h2><p>The quick brown fox.</p><p>Second paragraph.</p>",
        },
        headers=headers,
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    amend_res = await client.post(
        f"/api/organisations/review-html-org/documents/{doc_id}/amendments",
        json={
            "original_text": "quick brown fox",
            "proposed_text": "swift red fox",
        },
        headers=headers,
    )
    assert amend_res.status_code == 201
    amendment_id = amend_res.json()["id"]

    accept_res = await client.put(
        f"/api/organisations/review-html-org/documents/{doc_id}/amendments/{amendment_id}/status",
        json={"status": "accepted"},
        headers=headers,
    )
    assert accept_res.status_code == 200

    review_res = await client.get(
        f"/api/organisations/review-html-org/documents/{doc_id}/review",
        headers=headers,
    )
    assert review_res.status_code == 200

    data = review_res.json()
    diff_text = " ".join(token["text"] for token in data["full_diff_tokens"])

    assert data["original_body"].startswith("<h2>Scope</h2>")
    assert data["consolidated_body"].startswith("<h2>Scope</h2>")
    assert "<h2>" not in diff_text
    assert "<p>" not in diff_text
    assert "Scope" in diff_text
    assert "Second paragraph." in diff_text
    assert "swift red" in diff_text
    assert any(
        token["type"] == "insert" and "swift red" in token["text"]
        for token in data["full_diff_tokens"]
    )


@pytest.mark.asyncio
async def test_extract_pdf_ignores_bottom_footnotes_and_page_numbers(client):
    """PDF extraction drops footer footnotes and standalone page numbers."""
    jwt = await _register_and_login(client, "pdfimport-footnote@example.com")
    await _create_org(client, jwt, "pdf-footnote-org")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "Main body paragraph for the imported document.\n\n"
        "Second paragraph that should remain in the editor.",
    )
    pdf.set_y(-35)
    pdf.set_font("Helvetica", size=8)
    pdf.multi_cell(0, 4, "1. Transitional footnote about annex references.")
    pdf.set_y(-15)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, "1", align="C")
    pdf_bytes = bytes(pdf.output())

    res = await client.post(
        "/api/organisations/pdf-footnote-org/documents/extract-pdf",
        files={"file": ("agenda.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert "Main body paragraph for the imported document." in data["html"]
    assert "Second paragraph that should remain in the editor." in data["html"]
    assert "Transitional footnote about annex references." not in data["html"]
    assert "<p>1</p>" not in data["html"]


@pytest.mark.asyncio
async def test_extract_pdf_ignores_repeated_footer_text(client):
    """PDF extraction drops footer text that repeats at the bottom of multiple pages."""
    jwt = await _register_and_login(client, "pdfimport-repeated-footer@example.com")
    await _create_org(client, jwt, "pdf-repeated-footer-org")

    pdf = FPDF()
    pdf.set_auto_page_break(False)

    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "First page body paragraph that should stay in the import.")
    pdf.set_y(-18)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, "Confidential draft - Amendly working copy", align="C")

    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Second page body paragraph that should also stay in the import.")
    pdf.set_y(-18)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, "Confidential draft - Amendly working copy", align="C")

    pdf_bytes = bytes(pdf.output())

    res = await client.post(
        "/api/organisations/pdf-repeated-footer-org/documents/extract-pdf",
        files={"file": ("agenda.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert "First page body paragraph that should stay in the import." in data["html"]
    assert "Second page body paragraph that should also stay in the import." in data["html"]
    assert "Confidential draft - Amendly working copy" not in data["html"]


@pytest.mark.asyncio
async def test_create_document_empty_title_returns_422(client):
    """Empty title string returns 422 Unprocessable Entity."""
    jwt = await _register_and_login(client, "emptytitle@example.com")
    await _create_org(client, jwt, "emptytitle-org")

    res = await client.post(
        "/api/organisations/emptytitle-org/documents",
        json={"title": "   "},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_document_org_not_found(client):
    """Creating a document in a non-existent org returns 404."""
    jwt = await _register_and_login(client, "noorg@example.com")

    res = await client.post(
        "/api/organisations/does-not-exist/documents",
        json={"title": "Nowhere Doc"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/organisations/{slug}/documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents_empty(client):
    """New org has no documents — list returns empty items with total=0."""
    jwt = await _register_and_login(client, "listmpty@example.com")
    await _create_org(client, jwt, "list-empty-org")

    res = await client.get(
        "/api/organisations/list-empty-org/documents",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_documents_after_create(client):
    """After creating a document the list includes it."""
    jwt = await _register_and_login(client, "listafter@example.com")
    await _create_org(client, jwt, "listafter-org")
    await _create_doc(client, jwt, "listafter-org", "Alpha Doc")

    res = await client.get(
        "/api/organisations/listafter-org/documents",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Alpha Doc"


@pytest.mark.asyncio
async def test_list_documents_pagination(client):
    """Pagination returns correct page slices and total count."""
    jwt = await _register_and_login(client, "pagdocs@example.com")
    await _create_org(client, jwt, "pagdocs-org")
    # Upgrade to Pro so we can create more than FREE_TIER_DOCUMENT_LIMIT (3) docs
    await _upgrade_to_pro("pagdocs-org")

    # Create 25 documents
    for i in range(25):
        await _create_doc(client, jwt, "pagdocs-org", f"Doc {i:02d}")

    res1 = await client.get(
        "/api/organisations/pagdocs-org/documents?page=1",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["total"] == 25
    assert len(d1["items"]) == 20
    assert d1["page"] == 1

    res2 = await client.get(
        "/api/organisations/pagdocs-org/documents?page=2",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert len(d2["items"]) == 5
    assert d2["page"] == 2


@pytest.mark.asyncio
async def test_list_documents_unauthenticated(client):
    """Listing documents without a token returns 401 or 403."""
    res = await client.get("/api/organisations/some-org/documents")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_documents_non_member_returns_404(client):
    """Non-member gets 404 on document list (no disclosure)."""
    jwt_owner = await _register_and_login(client, "ldown@example.com")
    await _create_org(client, jwt_owner, "ldnonmember-org")
    await _create_doc(client, jwt_owner, "ldnonmember-org")

    jwt_outsider = await _register_and_login(client, "ldout@example.com")
    res = await client.get(
        "/api/organisations/ldnonmember-org/documents",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/organisations/{slug}/documents/{doc_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_success(client):
    """Owner can fetch a document by ID."""
    jwt = await _register_and_login(client, "getdoc@example.com")
    await _create_org(client, jwt, "getdoc-org")
    doc = await _create_doc(client, jwt, "getdoc-org", "Fetchable Doc")

    res = await client.get(
        f"/api/organisations/getdoc-org/documents/{doc['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["id"] == doc["id"]
    assert res.json()["title"] == "Fetchable Doc"


@pytest.mark.asyncio
async def test_get_document_not_found(client):
    """Fetching a non-existent doc ID returns 404."""
    jwt = await _register_and_login(client, "docnotfound@example.com")
    await _create_org(client, jwt, "dnf-org")

    res = await client.get(
        "/api/organisations/dnf-org/documents/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_document_non_member_returns_404(client):
    """Non-member gets 404 when fetching a document."""
    jwt_owner = await _register_and_login(client, "gdowner@example.com")
    await _create_org(client, jwt_owner, "gdnonmem-org")
    doc = await _create_doc(client, jwt_owner, "gdnonmem-org")

    jwt_outsider = await _register_and_login(client, "gdoutsider@example.com")
    res = await client.get(
        f"/api/organisations/gdnonmem-org/documents/{doc['id']}",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_document_unauthenticated(client):
    """Fetching a document without a token returns 401 or 403."""
    res = await client.get("/api/organisations/some-org/documents/some-id")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /api/organisations/{slug}/documents/{doc_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_document_title(client):
    """Owner can update a document's title."""
    jwt = await _register_and_login(client, "updtitle@example.com")
    await _create_org(client, jwt, "updtitle-org")
    doc = await _create_doc(client, jwt, "updtitle-org", "Original Title")

    res = await client.put(
        f"/api/organisations/updtitle-org/documents/{doc['id']}",
        json={"title": "Updated Title"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Title"
    assert res.json()["body"] is None  # body unchanged


@pytest.mark.asyncio
async def test_update_document_body(client):
    """Owner can update a document's body."""
    jwt = await _register_and_login(client, "updbody@example.com")
    await _create_org(client, jwt, "updbody-org")
    doc = await _create_doc(client, jwt, "updbody-org", "Body Test")

    res = await client.put(
        f"/api/organisations/updbody-org/documents/{doc['id']}",
        json={"body": "New body content"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Body Test"  # title unchanged
    assert res.json()["body"] == "New body content"


@pytest.mark.asyncio
async def test_patch_document_sections_can_update_closed_title_and_body_together(client):
    """Closed-document section edits can persist title and body atomically."""
    jwt = await _register_and_login(client, "closedsections@example.com")
    await _create_org(client, jwt, "closed-sections-org")
    doc = await _create_doc(client, jwt, "closed-sections-org", "Original Title")

    close_res = await client.put(
        f"/api/organisations/closed-sections-org/documents/{doc['id']}/status",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert close_res.status_code == 200

    res = await client.patch(
        f"/api/organisations/closed-sections-org/documents/{doc['id']}/sections",
        json={
            "title": "Updated Final Title",
            "body": "<h2>Final section</h2><p>Approved text.</p>",
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Updated Final Title"
    assert data["body"] == "<h2>Final section</h2><p>Approved text.</p>"
    assert data["status"] == "closed"


@pytest.mark.asyncio
async def test_update_document_unauthenticated(client):
    """Updating without a token returns 401 or 403."""
    res = await client.put(
        "/api/organisations/some-org/documents/some-id",
        json={"title": "No Auth"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_document_non_member_returns_404(client):
    """Non-member gets 404 when attempting to update a document."""
    jwt_owner = await _register_and_login(client, "updown@example.com")
    await _create_org(client, jwt_owner, "upd-nm-org")
    doc = await _create_doc(client, jwt_owner, "upd-nm-org")

    jwt_outsider = await _register_and_login(client, "updout@example.com")
    res = await client.put(
        f"/api/organisations/upd-nm-org/documents/{doc['id']}",
        json={"title": "Hijack"},
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_document_not_found(client):
    """Updating a non-existent doc returns 404."""
    jwt = await _register_and_login(client, "updnotfound@example.com")
    await _create_org(client, jwt, "updnf-org")

    res = await client.put(
        "/api/organisations/updnf-org/documents/00000000-0000-0000-0000-000000000000",
        json={"title": "Ghost"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_document_empty_title_returns_422(client):
    """Sending an empty title string to PUT returns 422."""
    jwt = await _register_and_login(client, "updempty@example.com")
    await _create_org(client, jwt, "updempty-org")
    doc = await _create_doc(client, jwt, "updempty-org", "Valid Title")

    res = await client.put(
        f"/api/organisations/updempty-org/documents/{doc['id']}",
        json={"title": ""},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422
