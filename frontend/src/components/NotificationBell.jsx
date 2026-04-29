/**
 * NotificationBell — in-app notification center for authenticated users.
 *
 * Displays a bell icon in the top-right of the app navigation bar.
 * When the user has unread notifications a red badge shows the count.
 *
 * On click:
 *   1. Opens a glassmorphism dropdown (right-aligned, 380px wide).
 *   2. Calls POST /api/me/notifications/read to mark all as read.
 *   3. Lists the latest activity from the user's team+ organisations.
 *
 * Plan gating:
 *   Users who belong only to solo-plan orgs see an upgrade nudge instead
 *   of the notification list.
 *
 * Polling:
 *   Unread count is refreshed every 60 seconds in the background so the
 *   badge stays current without requiring a page reload.
 *
 * Props:
 *   orgSlug {string|null} - Optional slug of the current org, used to build
 *                           "upgrade" links.  Pass null on Dashboard.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { notificationClient } from '../lib/organisations'
import { useTranslation } from '../hooks/useTranslation'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Format an ISO timestamp as a relative string ("Just now", "3 min ago", etc.).
 *
 * @param {string} iso - ISO-8601 date string.
 * @param {function} t - Translation function.
 * @returns {string} Human-readable relative time.
 */
function relativeTime(iso, t) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return t('notifications.just_now')
  if (diff < 3600) return `${Math.floor(diff / 60)} min`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h`
  return `${Math.floor(diff / 86400)} d`
}

/**
 * Build a human-readable notification sentence from action + context.
 *
 * @param {object} item - Notification item from the API.
 * @param {function} t  - Translation function.
 * @returns {string}
 */
function buildLabel(item, t) {
  const actor = item.actor_name ?? '?'
  const doc = item.doc_title ?? '—'
  const key = `notifications.action_${item.action}`
  const fallback = t('notifications.action_unknown').replace('{doc}', doc)
  const raw = t(key)
  if (!raw || raw === key) return fallback
  return raw.replace('{actor}', actor).replace('{doc}', doc)
}

/**
 * Return a Tailwind colour class for the action dot.
 *
 * @param {string} action
 * @returns {string}
 */
function actionColour(action) {
  if (action === 'amendment_accepted') return 'bg-tertiary-fixed'
  if (action === 'amendment_rejected') return 'bg-error-container'
  if (action === 'amendment_submitted') return 'bg-primary-fixed'
  if (action === 'amendment_commented') return 'bg-secondary-container'
  return 'bg-surface-container-highest'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 60_000

export default function NotificationBell({ orgSlug = null }) {
  const { t } = useTranslation()

  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)   // { has_team_plan, items, unread_count }
  const [loading, setLoading] = useState(false)

  const dropdownRef = useRef(null)

  // ----- fetch helpers -----

  const fetchNotifications = useCallback(async () => {
    try {
      const result = await notificationClient.list(20)
      setData(result)
    } catch {
      // Silently ignore — bell should never crash the page
    }
  }, [])

  const fetchUnreadCount = useCallback(async () => {
    try {
      const result = await notificationClient.list(1)
      setData(prev => prev
        ? { ...prev, unread_count: result.unread_count, has_team_plan: result.has_team_plan }
        : result
      )
    } catch {
      // Silently ignore
    }
  }, [])

  // ----- initial load + polling -----

  useEffect(() => {
    fetchUnreadCount()

    const pollTimer = setInterval(fetchUnreadCount, POLL_INTERVAL_MS)
    return () => clearInterval(pollTimer)
  }, [fetchUnreadCount])

  // ----- close on outside click -----

  useEffect(() => {
    if (!open) return
    function handleOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [open])

  // ----- open handler -----

  async function handleOpen() {
    if (open) { setOpen(false); return }

    setOpen(true)
    setLoading(true)
    await fetchNotifications()
    setLoading(false)

    // Mark as read after the dropdown opens
    try {
      await notificationClient.markRead()
      setData(prev => prev ? { ...prev, unread_count: 0 } : prev)
    } catch {
      // Ignore — read tracking is best-effort
    }
  }

  const unreadCount = data?.unread_count ?? 0

  // ----- render -----

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={handleOpen}
        aria-label={t('notifications.title')}
        className="relative p-2 rounded-lg text-on-surface hover:bg-surface-container-low transition-colors"
      >
        {/* Bell SVG */}
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>

        {/* Unread badge */}
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 rounded-full bg-amendly-blue text-white font-body text-[10px] leading-none select-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute right-0 mt-2 w-[380px] z-50 rounded-xl overflow-hidden"
          style={{
            background: 'rgba(247,249,251,0.92)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            boxShadow: '0px 12px 32px rgba(42,52,57,0.10)',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-surface-container-highest">
            <span className="font-display text-title-sm text-amendly-dark font-semibold">
              {t('notifications.title')}
            </span>
          </div>

          {/* Body */}
          <div className="max-h-[420px] overflow-y-auto">
            {loading ? (
              <LoadingState />
            ) : !data?.has_team_plan ? (
              <UpgradeNudge t={t} orgSlug={orgSlug} />
            ) : data.items.length === 0 ? (
              <EmptyState t={t} />
            ) : (
              <ul>
                {data.items.map(item => (
                  <NotificationItem
                    key={item.id}
                    item={item}
                    t={t}
                    onClose={() => setOpen(false)}
                    onMarkRead={() =>
                      setData(prev => prev
                        ? {
                            ...prev,
                            items: prev.items.map(i =>
                              i.id === item.id ? { ...i, is_read: true } : i
                            ),
                          }
                        : prev
                      )
                    }
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-10">
      <span className="w-5 h-5 border-2 border-amendly-blue border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

/**
 * Empty state shown when the user has no recent notifications.
 * @param {{ t: function }} props
 */
function EmptyState({ t }) {
  return (
    <div className="px-4 py-8 text-center">
      <p className="font-body text-body-md text-amendly-gray">{t('notifications.empty')}</p>
    </div>
  )
}

/**
 * Upgrade nudge for solo-plan users.
 * @param {{ t: function, orgSlug: string|null }} props
 */
function UpgradeNudge({ t, orgSlug }) {
  const upgradeHref = orgSlug ? `/orgs/${orgSlug}/billing` : '/pricing'
  return (
    <div className="px-5 py-6 text-center flex flex-col items-center gap-3">
      {/* Star icon */}
      <div className="w-10 h-10 rounded-full bg-primary-fixed flex items-center justify-center">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      </div>
      <p className="font-display text-title-sm text-amendly-dark font-semibold">
        {t('notifications.upgrade_title')}
      </p>
      <p className="font-body text-body-md text-on-surface max-w-[280px]">
        {t('notifications.upgrade_body')}
      </p>
      <Link
        to={upgradeHref}
        className="mt-1 inline-block px-4 py-2 rounded-lg bg-amendly-blue text-white font-body text-body-md font-medium hover:opacity-90 transition-opacity"
      >
        {t('notifications.upgrade_cta')}
      </Link>
    </div>
  )
}

/**
 * One notification row.
 *
 * Props:
 *   item       {object}   - Notification from the API.
 *   t          {function} - Translation function.
 *   onClose    {function} - Called when the user navigates away from this row.
 *   onMarkRead {function} - Called to optimistically mark this item as read.
 */
function NotificationItem({ item, t, onClose, onMarkRead }) {
  let href = item.doc_id
    ? `/orgs/${item.org_slug}/documents/${item.doc_id}`
    : `/orgs/${item.org_slug}`

  if (item.amendment_id && item.doc_id) {
    href += `#amendment-${item.amendment_id}`
  }

  function handleClick() {
    if (!item.is_read) onMarkRead?.()
    onClose()
  }

  return (
    <li>
      <Link
        to={href}
        onClick={handleClick}
        className={`flex items-start gap-3 px-4 py-3 hover:bg-surface-container-low transition-colors ${
          item.is_read ? 'opacity-60' : ''
        }`}
      >
        {/* Colour dot */}
        <span
          className={`mt-1 flex-shrink-0 w-2 h-2 rounded-full ${actionColour(item.action)}`}
          aria-hidden="true"
        />

        <div className="flex-1 min-w-0">
          <p className="font-body text-body-md text-on-surface leading-snug line-clamp-2">
            {buildLabel(item, t)}
          </p>
          <p className="mt-0.5 font-body text-label-sm text-amendly-gray tracking-[0.02em]">
            {relativeTime(item.created_at, t)}
            {' · '}
            {t('notifications.in_org').replace('{org}', item.org_name)}
          </p>
        </div>
      </Link>
    </li>
  )
}
