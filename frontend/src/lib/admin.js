import { authFetch } from './api'

/**
 * Billing API client — thin wrapper around /api/billing/*.
 */
export const billingClient = {
  createCheckoutSession: async (slug, successUrl, cancelUrl, planName = 'solo', annual = false) => {
    const res = await authFetch('/api/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ slug, success_url: successUrl, cancel_url: cancelUrl, plan_name: planName, annual }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  createPortalSession: async (slug) => {
    const res = await authFetch('/api/billing/portal', {
      method: 'POST',
      body: JSON.stringify({ slug }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },
}

/**
 * Plan configuration API client.
 */
export const planClient = {
  getPlans: async () => {
    const res = await fetch('/api/plans')
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  adminListPlans: async () => {
    const res = await authFetch('/api/admin/plans')
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  adminGetStats: async () => {
    const res = await authFetch('/api/admin/stats')
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  adminListOrgs: async () => {
    const res = await authFetch('/api/admin/organisations')
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  adminUpdateOrgPlan: async (orgId, plan) => {
    const res = await authFetch(`/api/admin/organisations/${orgId}/plan`, {
      method: 'PATCH',
      body: JSON.stringify({ plan }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  adminUpdatePlan: async (planName, payload) => {
    const res = await authFetch(`/api/admin/plans/${planName}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },
}

/**
 * API client for /api/admin/users (superuser only).
 */
export const userAdminClient = {
  list: async ({ search, plan, includeDeleted } = {}) => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (plan) params.set('plan', plan)
    if (includeDeleted) params.set('include_deleted', 'true')
    const qs = params.toString()
    const res = await authFetch(`/api/admin/users${qs ? `?${qs}` : ''}`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  update: async (userId, payload) => {
    const res = await authFetch(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },
}

/**
 * API client for /api/admin/email-templates (superuser only).
 */
export const emailTemplateClient = {
  list: async () => {
    const res = await authFetch('/api/admin/email-templates')
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  upsert: async (key, payload) => {
    const res = await authFetch(`/api/admin/email-templates/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  reset: async (key) => {
    const res = await authFetch(`/api/admin/email-templates/${key}`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },
}

/**
 * API client for /api/admin/prospects (superuser only).
 */
export const prospectClient = {
  list: async () => {
    const res = await authFetch('/api/admin/prospects')
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  create: async (payload) => {
    const res = await authFetch('/api/admin/prospects', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  update: async (id, payload) => {
    const res = await authFetch(`/api/admin/prospects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },

  delete: async (id) => {
    const res = await authFetch(`/api/admin/prospects/${id}`, { method: 'DELETE' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    }
  },

  sendEmail: async (id, payload) => {
    const res = await authFetch(`/api/admin/prospects/${id}/email`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
    return data
  },
}
