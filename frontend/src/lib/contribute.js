/**
 * Public contribution API client — no auth required.
 *
 * Wraps the unauthenticated /api/contribute/{token} endpoints used by the
 * PublicContribution page.  These calls deliberately omit the Authorization
 * header so they work without an Amendly account.
 */

import { publicJsonFetch } from './api'

/**
 * Fetch the public document preview for a contribution token.
 *
 * @param {string} token - 64-char hex contributor token from the URL.
 * @returns {Promise<{ doc_id: string; title: string; body: string | null; status: string; org_name: string; contributor_link_status: 'active' | 'expired'; contributor_token_expires_at: string | null }>}
 * @throws {Error} With a message from the API error response body.
 */
export async function getPublicDocument(token) {
  return publicJsonFetch(`/api/contribute/${encodeURIComponent(token)}`)
}

/**
 * Submit an anonymous amendment via the public contribution token.
 *
 * @param {string} token - 64-char hex contributor token from the URL.
 * @param {{
 *   amendment_type: 'text_change' | 'general_comment';
 *   section?: string | null;
 *   original_text?: string | null;
 *   proposed_text?: string | null;
 *   justification?: string | null;
 *   contributor_name: string;
 *   contributor_email?: string | null;
 *   cf_turnstile_token?: string | null;
 * }} payload - Amendment data including contributor identity.
 * @returns {Promise<object>} AmendmentResponse for the created amendment.
 * @throws {Error} With a message from the API error response body.
 */
export async function submitPublicAmendment(token, payload) {
  return publicJsonFetch(`/api/contribute/${encodeURIComponent(token)}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
