/**
 * AdminUsers — superadmin user management page.
 *
 * Route: /admin/users
 *
 * Features:
 *   - Filterable list of all users (search by email/name, filter by plan,
 *     toggle deleted accounts).
 *   - Inline edit modal: override plan and plan_expires_at per user
 *     (for gifts or compensation).
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *
 * Props: none
 */

import { useEffect, useState, useCallback } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { userAdminClient } from '../lib/admin'

// ---------------------------------------------------------------------------
// Plan badge
// ---------------------------------------------------------------------------

function PlanBadge({ plan }) {
  const styles = {
    solo:         'bg-surface-container-highest text-on-surface',
    team:         'bg-primary-fixed text-on-primary-fixed',
    organisation: 'bg-tertiary-fixed text-on-tertiary-fixed',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[plan] ?? styles.solo}`}
    >
      {plan}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Admin nav (shared layout)
// ---------------------------------------------------------------------------

function AdminNav({ active }) {
  const links = [
    { to: '/admin/dashboard', label: 'Dashboard' },
    { to: '/admin/pricing', label: 'Plans' },
    { to: '/admin/email-templates', label: 'Emails' },
    { to: '/admin/prospects', label: 'Prospects' },
    { to: '/admin/users', label: 'Utilisateurs' },
  ]
  return (
    <header className="bg-surface-container-lowest shadow-ambient">
      <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
        <div>
          <p className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-0.5">
            Amendly · Superadmin
          </p>
          <h1 className="font-display text-headline-md text-on-surface tracking-[-0.01em]">
            Utilisateurs
          </h1>
        </div>
        <nav className="flex items-center gap-4">
          {links.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={`font-body text-body-md ${
                active === to
                  ? 'text-secondary border-b border-secondary pb-0.5'
                  : 'text-on-surface hover:text-secondary'
              }`}
            >
              {label}
            </Link>
          ))}
          <Link
            to="/dashboard"
            className="font-body text-body-md text-outline hover:text-on-surface"
          >
            ← App
          </Link>
        </nav>
      </div>
    </header>
  )
}

// ---------------------------------------------------------------------------
// Edit modal
// ---------------------------------------------------------------------------

const PLANS = ['solo', 'team', 'organisation']

function EditUserModal({ user, onClose, onSaved }) {
  const [plan, setPlan] = useState(user.plan)
  const [expiresAt, setExpiresAt] = useState(
    user.plan_expires_at ? user.plan_expires_at.slice(0, 16) : ''
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const payload = {}
      if (plan !== user.plan) payload.plan = plan
      // Always send plan_expires_at so it can be cleared
      payload.plan_expires_at = expiresAt ? new Date(expiresAt).toISOString() : ''
      const updated = await userAdminClient.update(user.id, payload)
      onSaved(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-on-surface/20 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-container-lowest rounded-2xl shadow-elevated w-full max-w-md mx-4 p-8"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-1">
          Modifier l'abonnement
        </h2>
        <p className="font-body text-body-md text-outline mb-6 truncate">{user.email}</p>

        <div className="space-y-5">
          <div>
            <label className="block font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-2">
              Plan
            </label>
            <div className="flex gap-2">
              {PLANS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPlan(p)}
                  className={`flex-1 py-2 rounded-lg font-body text-body-md transition-colors ${
                    plan === p
                      ? 'bg-amendly-blue text-white'
                      : 'bg-surface-container text-on-surface hover:bg-surface-container-highest'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-2">
              Expiration du plan
              <span className="ml-2 normal-case tracking-normal text-outline/70">
                (laisser vide = aucune expiration)
              </span>
            </label>
            <input
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full bg-surface-container rounded-lg px-4 py-2 font-body text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-amendly-blue"
            />
          </div>
        </div>

        {error && (
          <p className="mt-4 font-body text-body-md text-error">{error}</p>
        )}

        <div className="mt-8 flex gap-3 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg font-body text-body-md text-secondary hover:bg-surface-container"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-amendly-blue text-white font-body text-body-md disabled:opacity-50"
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminUsers() {
  const navigate = useNavigate()
  const location = useLocation()

  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [includeDeleted, setIncludeDeleted] = useState(false)

  const [editingUser, setEditingUser] = useState(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await userAdminClient.list({ search, plan: planFilter, includeDeleted })
      setUsers(data)
    } catch (err) {
      if (err.message.includes('403')) {
        navigate('/dashboard', { replace: true })
        return
      }
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search, planFilter, includeDeleted, navigate])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  function handleSaved(updated) {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
    setEditingUser(null)
  }

  function formatDate(iso) {
    if (!iso) return '—'
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  return (
    <div className="min-h-screen bg-surface">
      <AdminNav active={location.pathname} />

      <main className="max-w-screen-xl mx-auto px-6 py-12">

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-8">
          <input
            type="text"
            placeholder="Rechercher email ou nom…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-[220px] bg-surface-container-lowest rounded-xl px-4 py-2.5 font-body text-body-md text-on-surface shadow-ambient focus:outline-none focus:ring-2 focus:ring-amendly-blue"
          />
          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            className="bg-surface-container-lowest rounded-xl px-4 py-2.5 font-body text-body-md text-on-surface shadow-ambient focus:outline-none focus:ring-2 focus:ring-amendly-blue"
          >
            <option value="">Tous les plans</option>
            <option value="solo">Solo</option>
            <option value="team">Team</option>
            <option value="organisation">Organisation</option>
          </select>
          <label className="flex items-center gap-2 font-body text-body-md text-on-surface cursor-pointer">
            <input
              type="checkbox"
              checked={includeDeleted}
              onChange={(e) => setIncludeDeleted(e.target.checked)}
              className="accent-amendly-blue"
            />
            Inclure les comptes supprimés
          </label>
        </div>

        {/* Table */}
        {loading ? (
          <p className="font-body text-body-md text-outline">Chargement…</p>
        ) : error ? (
          <p className="font-body text-body-md text-error">{error}</p>
        ) : (
          <div className="bg-surface-container-lowest rounded-2xl shadow-ambient overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-container">
                  <th className="px-6 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Nom
                  </th>
                  <th className="px-4 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Plan
                  </th>
                  <th className="px-4 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Expire le
                  </th>
                  <th className="px-4 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Inscrit le
                  </th>
                  <th className="px-4 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Orgs
                  </th>
                  <th className="px-4 py-3 text-left font-body text-label-sm text-outline tracking-[0.08em] uppercase">
                    Statut
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center font-body text-body-md text-outline">
                      Aucun utilisateur trouvé.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr
                      key={u.id}
                      className={`border-b border-surface-container last:border-0 hover:bg-surface-container/50 transition-colors ${
                        u.is_deleted ? 'opacity-50' : ''
                      }`}
                    >
                      <td className="px-6 py-3 font-body text-body-md text-on-surface">
                        <span className="flex items-center gap-1.5">
                          {u.email}
                          {u.is_superuser && (
                            <span className="text-label-sm text-amendly-blue font-body tracking-[0.02em] uppercase">
                              admin
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-body text-body-md text-on-surface">
                        {u.name ?? <span className="text-outline">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        <PlanBadge plan={u.plan} />
                      </td>
                      <td className="px-4 py-3 font-body text-body-md text-on-surface">
                        {u.plan_expires_at ? (
                          <span className={new Date(u.plan_expires_at) < new Date() ? 'text-error' : ''}>
                            {formatDate(u.plan_expires_at)}
                          </span>
                        ) : (
                          <span className="text-outline">Aucune</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-body text-body-md text-outline">
                        {formatDate(u.created_at)}
                      </td>
                      <td className="px-4 py-3 font-body text-body-md text-on-surface">
                        {u.org_count > 0 ? (
                          <span title={u.org_names.join(', ')}>{u.org_count}</span>
                        ) : (
                          <span className="text-outline">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {u.is_deleted ? (
                          <span className="font-body text-label-sm text-error uppercase tracking-[0.02em]">
                            Supprimé
                          </span>
                        ) : (
                          <span className="font-body text-label-sm text-outline uppercase tracking-[0.02em]">
                            Actif
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {!u.is_deleted && (
                          <button
                            type="button"
                            onClick={() => setEditingUser(u)}
                            className="font-body text-body-md text-secondary hover:underline"
                          >
                            Modifier
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Count */}
        {!loading && !error && (
          <p className="mt-4 font-body text-body-md text-outline">
            {users.length} utilisateur{users.length !== 1 ? 's' : ''}
          </p>
        )}
      </main>

      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
