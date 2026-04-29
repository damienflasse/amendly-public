/**
 * AdminDashboard — superadmin platform overview.
 *
 * Route: /admin/dashboard
 *
 * Accessible to platform superusers only. Non-superusers are redirected
 * to /dashboard on mount (403 response from the admin API).
 *
 * On mount it fetches in parallel:
 *   GET /api/admin/stats          — platform-level aggregated metrics.
 *   GET /api/admin/organisations  — all orgs with member/document/amendment counts.
 *
 * Features:
 *   - Stats cards: Total orgs, Total users, MRR estimé, breakdown par plan,
 *     total amendments, total open documents.
 *   - Sparkline: org registrations over the last 30 days.
 *   - Tableau de toutes les organisations : nom, slug, plan, membres, documents,
 *     amendments, dernière activité, Stripe customer ID, date de création.
 *   - Modification de plan par ligne (extension ou révocation).
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *
 * Props: none
 */

import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { planClient } from '../lib/organisations'

// ---------------------------------------------------------------------------
// Plan badge (same visual tokens as OrgDetail)
// ---------------------------------------------------------------------------

/**
 * @param {{ plan: string }} props
 */
function PlanBadge({ plan }) {
  const styles = {
    solo:         'bg-surface-container-highest text-on-surface',
    team:         'bg-primary-fixed text-on-primary-fixed',
    organisation: 'bg-tertiary-fixed text-on-tertiary-fixed',
  }
  const labels = { solo: 'Solo', team: 'Team', organisation: 'Organisation' }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[plan] ?? styles.solo}`}
    >
      {labels[plan] ?? plan}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

/**
 * Single KPI card.
 *
 * @param {{ label: string; value: string | number; sub?: string }} props
 */
function StatCard({ label, value, sub }) {
  return (
    <div className="bg-surface-container-lowest rounded-md shadow-ambient px-6 py-5">
      <p className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-1">
        {label}
      </p>
      <p className="font-display text-display-sm text-on-surface tracking-[-0.02em]">
        {value}
      </p>
      {sub && (
        <p className="font-body text-label-sm text-outline mt-1">{sub}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sparkline — org registrations last 30 days
// ---------------------------------------------------------------------------

/**
 * Minimal inline SVG bar chart showing daily org-registration counts.
 *
 * @param {{ data: Array<{ date: string; count: number }> }} props
 */
function Sparkline({ data }) {
  if (!data || data.length === 0) return null

  const maxCount = Math.max(...data.map((d) => d.count), 1)
  const width = 320
  const height = 48
  const barW = Math.floor(width / data.length) - 1

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      aria-label="Inscriptions des 30 derniers jours"
      role="img"
    >
      {data.map((point, i) => {
        const barH = Math.max(2, Math.round((point.count / maxCount) * height))
        const x = i * (barW + 1)
        const y = height - barH
        return (
          <rect
            key={point.date}
            x={x}
            y={y}
            width={barW}
            height={barH}
            rx="1"
            fill={point.count > 0 ? '#1a4bd4' : '#d9e4ea'}
            opacity={point.count > 0 ? 0.85 : 1}
          >
            <title>{`${point.date} : ${point.count} org${point.count !== 1 ? 's' : ''}`}</title>
          </rect>
        )
      })}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Plan selector + apply button (per org row)
// ---------------------------------------------------------------------------

/**
 * Inline plan-change control for a single organisation row.
 *
 * Props:
 *   org       — AdminOrgResponse from the API.
 *   onUpdated — Called with the updated org object after a successful PATCH.
 */
function PlanSelector({ org, onUpdated }) {
  const [selected, setSelected] = useState(org.plan)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Determine the action label based on direction
  function actionLabel() {
    const order = { solo: 0, team: 1, organisation: 2 }
    if (selected === org.plan) return null
    return order[selected] > order[org.plan] ? 'Extension' : 'Révocation'
  }

  async function handleApply() {
    if (selected === org.plan) return
    const label = actionLabel()
    const confirmed = window.confirm(
      `${label} — passer "${org.name}" du plan ${org.plan} → ${selected} ?\n\nCette action modifie directement la base de données (sans interaction Stripe).`
    )
    if (!confirmed) return

    setSaving(true)
    setError(null)
    try {
      const updated = await planClient.adminUpdateOrgPlan(org.id, selected)
      onUpdated(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const label = actionLabel()

  return (
    <div className="flex items-center gap-2">
      <select
        value={selected}
        disabled={saving}
        onChange={(e) => setSelected(e.target.value)}
        className="bg-surface-container-highest text-on-surface font-body text-body-md rounded-md px-3 py-1 focus:outline-none focus:ring-2 focus:ring-secondary disabled:opacity-50"
      >
        <option value="solo">Solo</option>
        <option value="team">Team</option>
        <option value="organisation">Organisation</option>
      </select>

      {label && (
        <button
          type="button"
          disabled={saving}
          onClick={handleApply}
          className={`px-3 py-1 rounded-md font-body text-body-md transition-colors disabled:opacity-50 ${
            label === 'Extension'
              ? 'bg-primary-fixed text-on-primary-fixed hover:opacity-80'
              : 'bg-error-container/60 text-on-error-container hover:bg-error-container'
          }`}
        >
          {saving ? '…' : label}
        </button>
      )}

      {error && (
        <span className="font-body text-label-sm text-on-error-container">{error}</span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminDashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const [statsData, orgsData] = await Promise.all([
          planClient.adminGetStats(),
          planClient.adminListOrgs(),
        ])
        setStats(statsData)
        setOrgs(orgsData)
      } catch (err) {
        if (err.message?.includes('403') || err.message?.toLowerCase().includes('forbidden')) {
          navigate('/dashboard')
          return
        }
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [navigate])

  function handleOrgUpdated(updated) {
    setOrgs((prev) => prev.map((o) => (o.id === updated.id ? updated : o)))
  }

  // Derived: MRR formatted
  const mrrFormatted = stats
    ? new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(
        stats.estimated_mrr_cents / 100
      )
    : '—'

  // Filtered orgs
  const filteredOrgs = orgs.filter((o) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      o.name.toLowerCase().includes(q) ||
      o.slug.toLowerCase().includes(q) ||
      o.plan.toLowerCase().includes(q) ||
      (o.stripe_customer_id ?? '').toLowerCase().includes(q)
    )
  })

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="font-body text-body-md text-outline">Chargement…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="font-body text-body-md text-on-error-container">{error}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* ── Top bar ── */}
      <header className="bg-surface-container-lowest shadow-ambient">
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <p className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-0.5">
              Amendly · Superadmin
            </p>
            <h1 className="font-display text-headline-md text-on-surface tracking-[-0.01em]">
              Dashboard
            </h1>
          </div>
          <nav className="flex items-center gap-4">
            <Link
              to="/admin/dashboard"
              className="font-body text-body-md text-secondary border-b border-secondary pb-0.5"
            >
              Dashboard
            </Link>
            <Link
              to="/admin/pricing"
              className="font-body text-body-md text-on-surface hover:text-secondary"
            >
              Plans
            </Link>
            <Link
              to="/admin/email-templates"
              className="font-body text-body-md text-on-surface hover:text-secondary"
            >
              Emails
            </Link>
            <Link
              to="/admin/prospects"
              className="font-body text-body-md text-on-surface hover:text-secondary"
            >
              Prospects
            </Link>
            <Link
              to="/admin/users"
              className="font-body text-body-md text-on-surface hover:text-secondary"
            >
              Utilisateurs
            </Link>
            <Link
              to="/dashboard"
              className="font-body text-body-md text-outline hover:text-on-surface"
            >
              ← App
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-12 space-y-16">

        {/* ── Stats cards ── */}
        <section>
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-8">
            Vue d'ensemble
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
            <StatCard label="Organisations" value={stats?.total_orgs ?? '—'} />
            <StatCard label="Utilisateurs" value={stats?.total_users ?? '—'} />
            <StatCard
              label="MRR estimé"
              value={mrrFormatted}
              sub="Plans payants × tarif"
            />
            <StatCard
              label="Plans actifs"
              value={
                stats
                  ? (stats.orgs_by_plan.team ?? 0) + (stats.orgs_by_plan.organisation ?? 0)
                  : '—'
              }
              sub="Team + Organisation"
            />
            <StatCard
              label="Amendments"
              value={stats?.total_amendments ?? '—'}
              sub="Toutes orgs confondues"
            />
            <StatCard
              label="Docs ouverts"
              value={stats?.total_open_documents ?? '—'}
              sub="Status = open"
            />
          </div>

          {/* Plan breakdown + sparkline */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-0">
            {stats && (
              <div className="bg-surface-container-lowest rounded-md shadow-ambient px-6 py-5">
                <p className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-4">
                  Répartition par plan
                </p>
                <div className="flex flex-wrap gap-8">
                  {Object.entries(stats.orgs_by_plan)
                    .sort((a, b) => {
                      const order = { solo: 0, team: 1, organisation: 2 }
                      return (order[a[0]] ?? 9) - (order[b[0]] ?? 9)
                    })
                    .map(([plan, count]) => (
                      <div key={plan} className="flex items-center gap-3">
                        <PlanBadge plan={plan} />
                        <span className="font-display text-headline-sm text-on-surface">
                          {count}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {stats?.orgs_last_30_days && (
              <div className="bg-surface-container-lowest rounded-md shadow-ambient px-6 py-5">
                <p className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-3">
                  Inscriptions — 30 derniers jours
                </p>
                <Sparkline data={stats.orgs_last_30_days} />
                <p className="mt-2 font-body text-label-sm text-outline text-right">
                  Total :{' '}
                  {stats.orgs_last_30_days.reduce((s, d) => s + d.count, 0)} org
                  {stats.orgs_last_30_days.reduce((s, d) => s + d.count, 0) !== 1 ? 's' : ''}
                </p>
              </div>
            )}
          </div>
        </section>

        {/* ── Organisations table ── */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
              Organisations
              {orgs.length > 0 && (
                <span className="ml-2 font-body text-body-md text-outline">({orgs.length})</span>
              )}
            </h2>
            {/* Search */}
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrer par nom, slug, plan…"
              className="w-64 bg-surface-container-lowest rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary shadow-ambient"
            />
          </div>

          {filteredOrgs.length === 0 ? (
            <p className="font-body text-body-md text-outline">Aucune organisation trouvée.</p>
          ) : (
            <div className="bg-surface-container-lowest rounded-md shadow-ambient overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-container-highest">
                    <th className="text-left px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Organisation
                    </th>
                    <th className="text-left px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Plan
                    </th>
                    <th className="text-right px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Membres
                    </th>
                    <th className="text-right px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Docs
                    </th>
                    <th className="text-right px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Amendments
                    </th>
                    <th className="text-left px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Dernière activité
                    </th>
                    <th className="text-left px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Stripe ID
                    </th>
                    <th className="text-left px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Créée le
                    </th>
                    <th className="text-left px-5 py-3 font-body text-label-sm text-outline tracking-[0.06em] uppercase">
                      Modifier plan
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-highest">
                  {filteredOrgs.map((org) => (
                    <tr key={org.id} className="hover:bg-surface-container/40 transition-colors">
                      {/* Name + slug */}
                      <td className="px-5 py-3">
                        <p className="font-body text-body-md text-on-surface">{org.name}</p>
                        <p className="font-body text-label-sm text-outline">{org.slug}</p>
                      </td>

                      {/* Plan badge */}
                      <td className="px-5 py-3">
                        <PlanBadge plan={org.plan} />
                      </td>

                      {/* Member count */}
                      <td className="px-5 py-3 text-right font-body text-body-md text-on-surface">
                        {org.member_count}
                      </td>

                      {/* Document count */}
                      <td className="px-5 py-3 text-right font-body text-body-md text-on-surface">
                        {org.document_count}
                      </td>

                      {/* Amendment count */}
                      <td className="px-5 py-3 text-right font-body text-body-md text-on-surface">
                        {org.amendment_count ?? 0}
                      </td>

                      {/* Last activity */}
                      <td className="px-5 py-3 font-body text-body-md text-outline whitespace-nowrap">
                        {org.last_activity_at
                          ? new Date(org.last_activity_at).toLocaleDateString('fr-FR')
                          : <span className="italic">—</span>}
                      </td>

                      {/* Stripe customer ID */}
                      <td className="px-5 py-3">
                        {org.stripe_customer_id ? (
                          <span className="font-body text-label-sm text-outline font-mono">
                            {org.stripe_customer_id}
                          </span>
                        ) : (
                          <span className="font-body text-label-sm text-outline italic">—</span>
                        )}
                      </td>

                      {/* Created at */}
                      <td className="px-5 py-3 font-body text-body-md text-outline whitespace-nowrap">
                        {new Date(org.created_at).toLocaleDateString('fr-FR')}
                      </td>

                      {/* Plan selector */}
                      <td className="px-5 py-3">
                        <PlanSelector org={org} onUpdated={handleOrgUpdated} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
