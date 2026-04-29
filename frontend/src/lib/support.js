/**
 * Inbound messaging client for the public contact page and authenticated support.
 */

import { authJsonFetch, publicJsonFetch } from './api'

export const supportClient = {
  /**
   * Send a public contact message.
   *
   * @param {{ first_name: string, last_name: string, email: string, message: string, website?: string }} payload
   * @returns {Promise<{ ok: boolean }>}
   */
  sendContactMessage: (payload) =>
    publicJsonFetch('/api/contact', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /**
   * Send an authenticated support request.
   *
   * @param {{ category: string, subject: string, message: string }} payload
   * @returns {Promise<{ ok: boolean }>}
   */
  sendSupportRequest: (payload) =>
    authJsonFetch('/api/support', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
