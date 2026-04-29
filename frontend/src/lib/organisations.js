/**
 * Amendly Organisation API client — thin wrapper around /api/organisations/*.
 *
 * Mirrors the API contract from backend/app/api/organisations.py and
 * backend/app/api/documents.py.
 *
 * Usage:
 *   import { orgClient } from '@/lib/organisations'
 *   const orgs = await orgClient.listMyOrgs()
 *   const org  = await orgClient.createOrg({ name: 'ACME', slug: 'acme' })
 *   const docs = await orgClient.listDocuments('acme', 1)
 */

import { authFetch, authJsonFetch, buildApiError } from './api'

const API_BASE = '/api/organisations'

/**
 * Typed fetch wrapper for the organisations API.
 *
 * @param {string} path   - Path relative to API_BASE.
 * @param {RequestInit} [options] - Fetch options.
 * @returns {Promise<any>} Parsed JSON response body.
 * @throws {Error} With a message from the API error response body.
 */
async function apiFetch(path, options = {}) {
  return authJsonFetch(`${API_BASE}${path}`, options)
}

export const orgClient = {
  /**
   * List all organisations the current user belongs to with their role.
   *
   * @returns {Promise<Array<{ id: string; name: string; slug: string; plan: string; created_at: string; role: string }>>}
   */
  listMyOrgs: () => apiFetch('/me'),

  /**
   * Fetch a single organisation by slug.
   *
   * @param {string} slug
   * @returns {Promise<{ id: string; name: string; slug: string; plan: string; created_at: string }>}
   */
  getOrg: (slug) => apiFetch(`/${slug}`),

  /**
   * Update an organisation's name and/or slug. Requires owner role.
   *
   * @param {string} slug - Current organisation slug.
   * @param {{ name?: string; slug?: string }} payload
   * @returns {Promise<{ id: string; name: string; slug: string; plan: string; created_at: string }>}
   */
  updateOrg: (slug, payload) =>
    apiFetch(`/${slug}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  /**
   * Permanently delete an organisation. Requires owner role.
   *
   * @param {string} slug - Organisation slug.
   * @returns {Promise<void>}
   */
  deleteOrg: async (slug) => {
    const res = await authFetch(`${API_BASE}/${slug}`, { method: 'DELETE' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw buildApiError(res, data, `Request failed with status ${res.status}`)
    }
  },

  /**
   * Fetch activity counters for an organisation dashboard.
   *
   * @param {string} slug
   * @returns {Promise<{ active_docs: number; pending_amendments: number; member_count: number }>}
   */
  getOrgStats: (slug) => apiFetch(`/${slug}/stats`),

  /**
   * Create a new organisation. The caller automatically becomes the owner.
   *
   * @param {{ name: string; slug: string }} payload
   * @returns {Promise<{ id: string; name: string; slug: string; plan: string; created_at: string }>}
   */
  createOrg: (payload) =>
    apiFetch('', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /**
   * List documents for an organisation, paginated at 20 per page.
   *
   * @param {string} slug - Organisation slug.
   * @param {number} [page=1] - Page number (1-based).
   * @returns {Promise<{ items: Array; total: number; page: number; page_size: number }>}
   */
  listDocuments: (slug, page = 1) => apiFetch(`/${slug}/documents?page=${page}`),

  /**
   * Create a document inside an organisation. Requires owner or admin role.
   *
   * @param {string} slug - Organisation slug.
   * @param {{ title: string; body?: string | null }} payload
   * @returns {Promise<{ id: string; org_id: string; title: string; body: string | null; status: string; created_at: string }>}
   */
  createDocument: (slug, payload) =>
    apiFetch(`/${slug}/documents`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /**
   * Fetch a single document by ID.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @returns {Promise<{ id: string; org_id: string; title: string; body: string | null; status: string; created_at: string }>}
   */
  getDocument: (slug, docId) => apiFetch(`/${slug}/documents/${docId}`),

  /**
   * Update a document's title and/or body. Requires owner or admin role.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {{ title?: string; body?: string }} payload
   * @returns {Promise<{ id: string; org_id: string; title: string; body: string | null; status: string; created_at: string }>}
   */
  updateDocument: (slug, docId, payload) =>
    apiFetch(`/${slug}/documents/${docId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  /**
   * Update the section headings (h2/h3) of a document body and, optionally, its title.
   * Permitted when the document is in draft or closed status.
   * Requires owner or admin role.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {{ body: string; title?: string }} payload
   * @returns {Promise<{ id: string; org_id: string; title: string; body: string | null; status: string; created_at: string }>}
   */
  updateDocumentSections: (slug, docId, payload) =>
    apiFetch(`/${slug}/documents/${docId}/sections`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  /**
   * List amendments for a document, paginated at 20 per page.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {number} [page=1] - Page number (1-based).
   * @returns {Promise<{ items: Array; total: number; page: number; page_size: number }>}
   */
  listAmendments: (slug, docId, page = 1) =>
    apiFetch(`/${slug}/documents/${docId}/amendments?page=${page}`),

  /**
   * List only the current user's own amendments for a document, paginated at 20 per page.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {number} [page=1] - Page number (1-based).
   * @returns {Promise<{ items: Array; total: number; page: number; page_size: number }>}
   */
  listMyAmendments: (slug, docId, page = 1) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/mine?page=${page}`),

  /**
   * Submit a new amendment to a document. Any member may submit.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {{ original_text: string; proposed_text: string; section?: string | null; justification?: string | null }} payload
   * @returns {Promise<{ id: string; doc_id: string; section: string | null; original_text: string; proposed_text: string; justification: string | null; status: string; author_id: string; created_at: string }>}
   */
  createAmendment: (slug, docId, payload) =>
    apiFetch(`/${slug}/documents/${docId}/amendments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /**
   * Fetch a single amendment by ID.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @returns {Promise<{ id: string; doc_id: string; section: string | null; original_text: string; proposed_text: string; justification: string | null; status: string; author_id: string; created_at: string }>}
   */
  getAmendment: (slug, docId, amendmentId) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/${amendmentId}`),

  /**
   * Accept or reject an amendment. Requires owner or admin role.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @param {'accepted' | 'rejected'} newStatus - The new status to set.
   * @returns {Promise<{ id: string; doc_id: string; section: string | null; original_text: string; proposed_text: string; justification: string | null; status: string; author_id: string; created_at: string }>}
   */
  updateAmendmentStatus: (slug, docId, amendmentId, newStatus, decisionReason) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/${amendmentId}/status`, {
      method: 'PUT',
      body: JSON.stringify({
        status: newStatus,
        ...(decisionReason ? { decision_reason: decisionReason } : {}),
      }),
    }),

  /**
   * Update a document's lifecycle status. Requires owner or admin role.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {'draft' | 'open' | 'closed'} newStatus - The new document status.
   * @returns {Promise<{ id: string; org_id: string; title: string; body: string | null; status: string; created_at: string }>}
   */
  updateDocumentStatus: (slug, docId, newStatus) =>
    apiFetch(`/${slug}/documents/${docId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status: newStatus }),
    }),

  /**
   * Withdraw a pending amendment. Author only.
   *
   * Soft-deletes the amendment by setting its status to 'withdrawn'.
   * Returns void on 204 No Content.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @returns {Promise<void>}
   */
  withdrawAmendment: async (slug, docId, amendmentId) => {
    const res = await authFetch(
      `${API_BASE}/${slug}/documents/${docId}/amendments/${amendmentId}`,
      { method: 'DELETE' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw buildApiError(res, data, `Request failed with status ${res.status}`)
    }
  },

  /**
   * Fetch the word-level diff for an amendment.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @returns {Promise<{ tokens: Array<{ text: string; type: 'equal' | 'insert' | 'delete' }> }>}
   */
  getAmendmentDiff: (slug, docId, amendmentId) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/${amendmentId}/diff`),

  /**
   * React to an amendment (support or oppose). Toggle: posting the same type cancels it.
   *
   * Plan gating: team and organisation plans only. Returns 402 for solo.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @param {'support' | 'oppose'} type - Reaction type.
   * @returns {Promise<{ id: string; support_count: number; oppose_count: number; user_reaction: string | null }>}
   */
  reactToAmendment: (slug, docId, amendmentId, type) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/${amendmentId}/react`, {
      method: 'POST',
      body: JSON.stringify({ type }),
    }),

  /**
   * Fetch aggregated reaction counts across all pending amendments for a document.
   *
   * Plan gating: team and organisation plans only. Returns 402 for solo.
   * Intended for document owners and admins.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @returns {Promise<{ total_pending: number; support_count: number; oppose_count: number }>}
   */
  getReactionSummary: (slug, docId) =>
    apiFetch(`/${slug}/documents/${docId}/reaction-summary`),

  /**
   * Invite an email address to join an organisation. Requires owner or admin role.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} email - Email address of the invitee.
   * @param {string | null} [turnstileToken=null] - Optional Turnstile token.
   * @returns {Promise<{ id: string; org_id: string; email: string; created_at: string; expires_at: string; accepted_at: string | null }>}
   */
  inviteMember: (slug, email, turnstileToken = null) =>
    apiFetch(`/${slug}/invite`, {
      method: 'POST',
      body: JSON.stringify({ email, ...(turnstileToken ? { turnstile_token: turnstileToken } : {}) }),
    }),

  /**
   * Get the consolidated document body with all accepted amendments applied.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @returns {Promise<{ title: string; body_with_amendments_applied: string; amendments_applied: number }>}
   */
  getConsolidated: (slug, docId) =>
    apiFetch(`/${slug}/documents/${docId}/consolidated`),

  /**
   * Fetch the full review payload for a document prior to export.
   *
   * Returns original body, consolidated body, full-document diff tokens,
   * amendment counts by status, and per-amendment detail for accepted items.
   * Available to all organisation members.
   *
   * @param {string} slug  - Organisation slug.
   * @param {string} docId - Document UUID.
   * @returns {Promise<{
   *   title: string;
   *   original_body: string;
   *   consolidated_body: string;
   *   full_diff_tokens: Array<{ text: string; type: 'equal' | 'insert' | 'delete' }>;
   *   count_accepted: number;
   *   count_pending: number;
   *   count_rejected: number;
   *   count_withdrawn: number;
   *   accepted_amendments: Array<{
   *     id: string;
   *     section: string | null;
   *     original_text: string | null;
   *     proposed_text: string | null;
   *     justification: string | null;
   *     author_name: string;
   *     created_at: string;
   *     diff_tokens: Array<{ text: string; type: 'equal' | 'insert' | 'delete' }>;
   *   }>;
   * }>}
   */
  getDocumentReview: (slug, docId) =>
    apiFetch(`/${slug}/documents/${docId}/review`),

  /**
   * Export the consolidated document (original body + accepted amendments) as a file.
   *
   * Triggers a browser download by creating a temporary <a> element.
   * Only owners and admins may export — the API returns 403 otherwise.
   *
   * @param {string} slug   - Organisation slug.
   * @param {string} docId  - Document UUID.
   * @param {'docx' | 'pdf' | 'txt' | 'csv' | 'json'} format - Desired file format (default: 'docx').
   * @param {'none' | 'accepted' | 'all'} includeAmendments - Whether to append an
   *   amendments section to the export (default: 'none').
   * @returns {Promise<void>} Resolves when the download has been triggered.
   * @throws {Error} If the API returns a non-2xx status.
   */
  exportDocument: async (slug, docId, format = 'docx', includeAmendments = 'none') => {
    const res = await authFetch(
      `${API_BASE}/${slug}/documents/${docId}/export?format=${format}&include_amendments=${includeAmendments}`,
      {}
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail ?? `Export failed with status ${res.status}`)
    }
    // Extract filename from Content-Disposition header, falling back to a safe default
    const disposition = res.headers.get('content-disposition') ?? ''
    const match = disposition.match(/filename="([^"]+)"/)
    const filename = match ? match[1] : `document.${format}`

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  /**
   * Export the consolidated document as a ZIP archive containing every format
   * available on the current plan.
   *
   * Triggers a browser download by creating a temporary <a> element.
   * Only owners and admins may export — the API returns 403 otherwise.
   *
   * @param {string} slug               - Organisation slug.
   * @param {string} docId              - Document UUID.
   * @param {'none'|'accepted'|'all'} [includeAmendments='none'] - Whether to append an amendments appendix.
   * @returns {Promise<void>} Resolves when the download has been triggered.
   * @throws {Error} If the API returns a non-2xx status.
   */
  exportDocumentZip: async (slug, docId, includeAmendments = 'none') => {
    const res = await authFetch(
      `${API_BASE}/${slug}/documents/${docId}/export/zip?include_amendments=${includeAmendments}`,
      {}
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail ?? `Export failed with status ${res.status}`)
    }
    const disposition = res.headers.get('content-disposition') ?? ''
    const match = disposition.match(/filename="([^"]+)"/)
    const filename = match ? match[1] : 'document.zip'

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  /**
   * Fetch public metadata about an invitation without authentication.
   *
   * Called on mount of the AcceptInvite page so the org name can be shown
   * before the user logs in. Returns 404 if the token is unknown and 400 if
   * it is expired or already accepted.
   *
   * @param {string} token - The invite token from the URL query parameter.
   * @returns {Promise<{ org_name: string; email: string; expires_at: string }>}
   */
  getInvitationPreview: async (token) => {
    const res = await fetch(
      `/api/invitations/preview?token=${encodeURIComponent(token)}`
    )
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw buildApiError(res, data, `Request failed with status ${res.status}`)
    return data
  },

  /**
   * List all members of an organisation. Any org member may call this.
   *
   * @param {string} slug - Organisation slug.
   * @returns {Promise<Array<{ user_id: string; email: string; name: string | null; role: string; joined_at: string }>>}
   */
  listMembers: (slug) => apiFetch(`/${slug}/members`),

  /**
   * Change the role of an organisation member. Owner only.
   * Valid roles: 'admin' | 'member'.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} userId - ID of the user whose role should change.
   * @param {'admin' | 'member'} role - The new role.
   * @returns {Promise<{ user_id: string; email: string; name: string | null; role: string; joined_at: string }>}
   */
  changeMemberRole: (slug, userId, role) =>
    apiFetch(`/${slug}/members/${userId}/role`, {
      method: 'PUT',
      body: JSON.stringify({ role }),
    }),

  /**
   * Remove a member from an organisation. Owner or admin only.
   * Cannot remove the owner.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} userId - ID of the user to remove.
   * @returns {Promise<void>} Resolves on 204 No Content.
   */
  removeMember: async (slug, userId) => {
    const res = await authFetch(`${API_BASE}/${slug}/members/${userId}`, { method: 'DELETE' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw buildApiError(res, data, `Request failed with status ${res.status}`)
    }
  },

  /**
   * Fetch a paginated page of activity feed entries for an organisation.
   *
   * Any authenticated member may call this endpoint.
   *
   * @param {string} slug - Organisation slug.
   * @param {number} [page=1] - 1-based page number.
   * @returns {Promise<{ items: Array<{ id: string; action: string; actor_name: string; doc_title: string | null; created_at: string }>; total: number; page: number; page_size: number }>}
   */
  getActivity: (slug, page = 1) => apiFetch(`/${slug}/activity?page=${page}`),

  /**
   * Download the full activity log for an organisation as a CSV file.
   *
   * Owner/admin only. Triggers a browser download of a CSV file containing
   * all activity entries ordered newest-first.
   *
   * @param {string} slug - Organisation slug.
   * @returns {Promise<void>} Resolves when the download has been triggered.
   * @throws {Error} If the API returns a non-2xx status.
   */
  exportActivity: async (slug) => {
    const res = await authFetch(`${API_BASE}/${slug}/activity/export`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail ?? `Export failed with status ${res.status}`)
    }
    const disposition = res.headers.get('content-disposition') ?? ''
    const match = disposition.match(/filename="([^"]+)"/)
    const filename = match ? match[1] : `activity-${slug}.csv`
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  /**
   * Accept or reject multiple pending amendments in a single request.
   *
   * Owner/admin only. Non-pending amendments in the list are silently skipped.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string[]} amendmentIds - Array of amendment UUIDs to update.
   * @param {'accepted' | 'rejected'} newStatus - The target status.
   * @param {string} [decisionReason] - Optional decision reason applied to all.
   * @returns {Promise<{ updated_count: number; skipped_count: number }>}
   */
  bulkUpdateAmendmentStatus: (slug, docId, amendmentIds, newStatus, decisionReason) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/bulk-status`, {
      method: 'PATCH',
      body: JSON.stringify({
        amendment_ids: amendmentIds,
        status: newStatus,
        ...(decisionReason ? { decision_reason: decisionReason } : {}),
      }),
    }),

  /**
   * Permanently delete a batch of documents. Owner only.
   *
   * @param {string} slug - Organisation slug.
   * @param {string[]} docIds - Array of document UUIDs to delete.
   * @returns {Promise<{ deleted: number }>} Number of documents actually deleted.
   */
  deleteDocuments: (slug, docIds) =>
    apiFetch(`/${slug}/documents`, {
      method: 'DELETE',
      body: JSON.stringify({ doc_ids: docIds }),
    }),

  /**
   * List all pending (non-expired, non-accepted) invitations for an organisation.
   * Owner/admin only.
   *
   * @param {string} slug - Organisation slug.
   * @returns {Promise<Array<{ id: string; org_id: string; email: string; created_at: string; expires_at: string; accepted_at: string | null }>>}
   */
  listInvitations: (slug) => apiFetch(`/${slug}/invitations`),

  /**
   * Revoke (delete) a pending invitation. Owner/admin only.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} invitationId - UUID of the invitation to revoke.
   * @returns {Promise<void>} Resolves on 204 No Content.
   */
  revokeInvitation: async (slug, invitationId) => {
    const res = await authFetch(`${API_BASE}/${slug}/invitations/${invitationId}`, { method: 'DELETE' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw buildApiError(res, data, `Request failed with status ${res.status}`)
    }
  },

  /**
   * Resend an invitation email, generating a fresh token and extending the expiry.
   * Owner/admin only.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} invitationId - UUID of the invitation to resend.
   * @returns {Promise<{ id: string; org_id: string; email: string; created_at: string; expires_at: string; accepted_at: string | null }>}
   */
  resendInvitation: (slug, invitationId) =>
    apiFetch(`/${slug}/invitations/${invitationId}/resend`, { method: 'POST' }),

  /**
   * Accept an organisation invitation by token.
   *
   * @param {string} token - The invite token from the URL query parameter.
   * @returns {Promise<{ id: string; org_id: string; email: string; accepted_at: string }>}
   */
  /**
   * List all comments on an amendment, ordered oldest-first.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @returns {Promise<{ items: Array<{ id: string; amendment_id: string; author_id: string | null; author_name: string | null; author_email: string | null; body: string; created_at: string }>; total: number }>}
   */
  listComments: (slug, docId, amendmentId) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/${amendmentId}/comments`),

  /**
   * Post a new comment on an amendment.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @param {string} body - Plain-text comment body (max 2 000 chars).
   * @returns {Promise<{ id: string; amendment_id: string; author_id: string | null; author_name: string | null; author_email: string | null; body: string; created_at: string }>}
   */
  postComment: (slug, docId, amendmentId, body) =>
    apiFetch(`/${slug}/documents/${docId}/amendments/${amendmentId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  /**
   * Delete a comment. Only the comment author or an org owner/admin may delete.
   *
   * @param {string} slug - Organisation slug.
   * @param {string} docId - Document UUID.
   * @param {string} amendmentId - Amendment UUID.
   * @param {string} commentId - Comment UUID.
   * @returns {Promise<void>} Resolves on 204 No Content.
   */
  deleteComment: async (slug, docId, amendmentId, commentId) => {
    const res = await authFetch(
      `${API_BASE}/${slug}/documents/${docId}/amendments/${amendmentId}/comments/${commentId}`,
      { method: 'DELETE' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw buildApiError(res, data, `Request failed with status ${res.status}`)
    }
  },

  acceptInvite: async (token, turnstileToken = null) => {
    const res = await authFetch('/api/invitations/accept', {
      method: 'POST',
      body: JSON.stringify({ token, ...(turnstileToken ? { turnstile_token: turnstileToken } : {}) }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw buildApiError(res, data, `Request failed with status ${res.status}`)
    return data
  },

  /**
   * Generate (or regenerate) a contributor public link token for a document.
   *
   * Owner/admin only. If a token already exists it is replaced (old link revoked).
   *
   * @param {string} slug  - Organisation slug.
   * @param {string} docId - Document UUID.
   * @returns {Promise<{ token: string; created_at: string; expires_at: string; url: string; status: 'active' }>}
   */
  generateContributorToken: (slug, docId) =>
    apiFetch(`/${slug}/documents/${docId}/contributor-token`, { method: 'POST' }),

  /**
   * Revoke the contributor public link for a document.
   *
   * Owner/admin only. Sets contributor_token to NULL immediately.
   *
   * @param {string} slug  - Organisation slug.
   * @param {string} docId - Document UUID.
   * @returns {Promise<{ token: null; created_at: null; expires_at: null; url: null; status: 'revoked' }>}
   */
  revokeContributorToken: (slug, docId) =>
    apiFetch(`/${slug}/documents/${docId}/contributor-token`, { method: 'DELETE' }),
}

export { billingClient, emailTemplateClient, planClient, prospectClient } from './admin'
export { notificationClient } from './notifications'
