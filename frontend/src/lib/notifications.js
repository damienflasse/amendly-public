import { authFetch } from './api'

/**
 * Notification center API client.
 */
export const notificationClient = {
  list: async (limit = 20) => {
    const res = await authFetch(`/api/me/notifications?limit=${limit}`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  markRead: async () => {
    const res = await authFetch('/api/me/notifications/read', {
      method: 'POST',
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },
}
