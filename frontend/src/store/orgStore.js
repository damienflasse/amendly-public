/**
 * orgStore — Zustand store for the current user's organisations.
 *
 * State:
 *   organisations  — Array of MembershipResponse objects from GET /api/organisations/me.
 *
 * Actions:
 *   setOrganisations(orgs)  — Replace the full organisations list.
 *
 * Each org entry has the shape:
 *   { id, name, slug, plan, created_at, role }
 *
 * The store is populated on Dashboard mount and cleared on logout.
 */

import { create } from 'zustand'

const useOrgStore = create((set) => ({
  /**
   * @type {Array<{ id: string; name: string; slug: string; plan: string; created_at: string; role: string }>}
   */
  organisations: [],

  /**
   * Replace the organisations list.
   * @param {Array<{ id: string; name: string; slug: string; plan: string; created_at: string; role: string }>} orgs
   */
  setOrganisations: (orgs) => set({ organisations: orgs }),
}))

export default useOrgStore
