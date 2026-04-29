/**
 * OrgDetail — organisation-scoped document list page.
 *
 * Route: /orgs/:slug
 *
 * On mount it fetches:
 *   1. GET /api/organisations/me                — determines the caller's role in this org.
 *   2. GET /api/organisations/{slug}            — loads org name + metadata.
 *   3. GET /api/organisations/{slug}/documents  — loads the paginated document list.
 *
 * Features:
 *   - Shows org name as the page headline with a plan badge (Free / Pro).
 *   - "Billing" link in header (owner only) → /orgs/:slug/billing.
 *   - Lists documents with title, status badge, and creation date.
 *   - Search input filters documents by title (client-side, current page).
 *   - Sort dropdown orders by date (newest/oldest), title (A→Z / Z→A), or status.
 *   - "New document" button opens an inline create form (title required, body optional).
 *   - "Invite member" button (owner/admin only) → inline form with email field.
 *   - Collapsible "Members" section below the documents list:
 *       • All members see avatar initials, name, email, and a role badge.
 *       • Owner sees a role selector (admin / member) and a remove button per row.
 *   - Collapsible "Recent activity" section at the bottom:
 *       • Fetches last 20 entries from GET /api/organisations/{slug}/activity.
 *       • Each entry: icon + "{actor} {verb} {document}" + relative time.
 *   - Clicking a document row navigates to /orgs/:slug/documents/:id.
 *   - Pagination controls for pages beyond the first.
 *   - Non-members are bounced to /dashboard (org returns 404).
 *
 * Design: "The Editorial Ledger" (frontend/DESIGN.md).
 *   - Tonal layering — surface base, cards on surface-container-lowest.
 *   - Manrope for headings, Inter for body/UI text.
 *   - Status badges use soft-fill colours (draft/open/closed).
 *   - No 1px borders; structure through background shifts and ambient shadows.
 *
 * Props: none (reads :slug from React Router params)
 * Side effects:
 *   - Uses cookie-backed authenticated API calls.
 *   - Fetches GET /api/me/notifications/settings to show a muted badge when
 *     the current user has notifications_muted=true for this org.
 *   - Navigates to /dashboard on 404 (non-member or org not found).
 *   - Navigates to /orgs/:slug/documents/:id on document click.
 */

import { useEffect, useRef, useState } from 'react'
import { Turnstile } from '@marsidev/react-turnstile'
import { Link, useNavigate, useParams } from 'react-router-dom'
import UpgradeCallout from '../components/UpgradeCallout'
import DocumentImportWorkflow from '../components/DocumentImportWorkflow'
import { DocumentStructurer } from '../components/DocumentStructureEditor'
import RichTextEditor from '../components/RichTextEditor'
import { authFetch } from '../lib/api'
import { autoProposeSectionsFromParagraphs } from '../lib/documentSections'
import { orgClient } from '../lib/organisations'
import {
  ACTION_ICONS,
  getDocumentUpgradeCallout,
  getSeatUpgradeCallout,
  relativeTime,
  restoreTriggerFocus,
} from './org-detail/utils'
import { getTurnstileSiteKey } from '../lib/turnstile'
import { getErrorMessage, isDocumentLimitError, isSeatBillingError } from '../lib/upgrade'
import { useTranslation } from '../hooks/useTranslation'
import LanguageSwitcher from '../components/LanguageSwitcher'
import NotificationBell from '../components/NotificationBell'
import useAuthStore from '../store/authStore'
import { useFilteredDocuments } from './org-detail/hooks'
import {
  DocumentsTabSection,
  MembersTabSection,
  OrgDetailHero,
  OrgDetailTabs,
} from './org-detail/sections'

// ---------------------------------------------------------------------------
// Plan badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge showing an organisation's billing plan.
 *
 * @param {{ plan: 'solo' | 'team' | 'organisation' }} props
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
// Status badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge showing a document's lifecycle status.
 * Uses i18n keys document.status_draft/open/closed for the label.
 *
 * @param {{ status: 'draft' | 'open' | 'closed'; t: Function }} props
 */
function StatusBadge({ status, t }) {
  const styles = {
    draft:  'bg-surface-container-highest text-on-surface',
    open:   'bg-primary-fixed text-on-primary-fixed',
    closed: 'bg-tertiary-fixed text-on-tertiary-fixed',
  }
  const label = t(`document.status_${status}`) || status
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[status] ?? styles.draft}`}
    >
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Invite member form (inline, owner/admin only)
// ---------------------------------------------------------------------------

/**
 * Inline form for inviting a new member by email address.
 *
 * Visible only to owners and admins. Shows a success message after a
 * successful invite to confirm the link was sent.
 *
 * Props:
 *   slug      — Organisation slug (used to call the API).
 *   userRole  — The current user's role in the organisation.
 *   onCancel  — Called when the user dismisses the form.
 *   t         — Translation function from useTranslation.
 */
function InviteMemberForm({ slug, userRole, onCancel, t }) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [lastEmail, setLastEmail] = useState('')
  const [turnstileToken, setTurnstileToken] = useState('')
  const formRef = useRef(null)
  const emailInputRef = useRef(null)
  const turnstileRef = useRef(null)
  const turnstileSiteKey = getTurnstileSiteKey()

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      if (!success) {
        emailInputRef.current?.focus({ preventScroll: true })
      }
    })

    return () => window.cancelAnimationFrame(frameId)
  }, [success])

  function handleKeyDown(event) {
    if (event.key !== 'Escape' || loading) return
    event.preventDefault()
    onCancel()
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await orgClient.inviteMember(slug, email.trim(), turnstileToken || null)
      setLastEmail(email.trim())
      setSuccess(true)
      setEmail('')
      turnstileRef.current?.reset()
      setTurnstileToken('')
    } catch (err) {
      turnstileRef.current?.reset()
      setTurnstileToken('')
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div
        ref={formRef}
        onKeyDown={handleKeyDown}
        className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mt-8"
      >
        <p className="font-body text-body-md text-on-surface mb-6">
          {t('org.invitation_sent').replace('{email}', lastEmail || t('org.email_placeholder'))}
        </p>
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => setSuccess(false)}
            className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md"
          >
            {t('org.invite_another')}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-8 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md"
          >
            {t('org.done')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={formRef}
      onKeyDown={handleKeyDown}
      className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mt-8"
    >
      <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-8">
        {t('org.invite_form_title')}
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('org.email_label')} <span className="text-secondary">*</span>
          </label>
          <input
            ref={emailInputRef}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            maxLength={255}
            placeholder={t('org.email_placeholder')}
            className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
          />
        </div>

        {error && isSeatBillingError(error) && (
          <UpgradeCallout
            {...getSeatUpgradeCallout({
              t,
              userRole,
              slug,
              note: getErrorMessage(error),
            })}
          />
        )}

        {error && !isSeatBillingError(error) && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
            {getErrorMessage(error)}
          </p>
        )}

        {turnstileSiteKey && (
          <Turnstile
            ref={turnstileRef}
            siteKey={turnstileSiteKey}
            onSuccess={(token) => setTurnstileToken(token)}
            onExpire={() => setTurnstileToken('')}
            onError={() => setTurnstileToken('')}
            options={{ theme: 'light', size: 'flexible', action: 'org_invite' }}
          />
        )}

        <div className="flex gap-4 pt-4">
          <button
            type="submit"
            disabled={loading || !email.trim()}
            className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50"
          >
            {loading ? t('org.sending_invite') : t('org.send_invitation')}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-8 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md"
          >
            {t('org.cancel')}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Create document form (inline)
// ---------------------------------------------------------------------------

/**
 * Inline form for creating a new document inside an organisation.
 *
 * Props:
 *   slug      — Organisation slug (used to call the API).
 *   userRole  — The current user's role in the organisation.
 *   onCreated — Called with the new document object after successful creation.
 *   onCancel  — Called when the user dismisses the form without saving.
 *   t         — Translation function from useTranslation.
 */
function CreateDocumentForm({ slug, userRole, onCreated, onCancel, t }) {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [importBusy, setImportBusy] = useState(false)
  const [showStructurer, setShowStructurer] = useState(false)
  const [importKey, setImportKey] = useState(0)
  const formRef = useRef(null)
  const titleInputRef = useRef(null)

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      titleInputRef.current?.focus({ preventScroll: true })
    })

    return () => window.cancelAnimationFrame(frameId)
  }, [])

  function handleKeyDown(event) {
    if (event.key !== 'Escape' || loading || importBusy) return
    event.preventDefault()
    onCancel()
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const doc = await orgClient.createDocument(slug, {
        title: title.trim(),
        body: body.trim() || null,
      })
      onCreated(doc)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      ref={formRef}
      onKeyDown={handleKeyDown}
      className="bg-surface-container-lowest rounded-md shadow-ambient p-8 mt-8"
    >
      <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em] mb-8">
        {t('org.new_doc_form_title')}
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Title */}
        <div>
          <label className="block font-body text-label-sm text-on-surface tracking-[0.02em] uppercase mb-2">
            {t('org.doc_title_label')} <span className="text-secondary">*</span>
          </label>
          <input
            ref={titleInputRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={500}
            placeholder={t('org.doc_title_placeholder')}
            className="w-full bg-surface rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary"
          />
        </div>

        {/* Actions — kept above the editor so they stay visible after import */}
        {error && isDocumentLimitError(error) && (
          <UpgradeCallout
            {...getDocumentUpgradeCallout({
              t,
              userRole,
              slug,
              note: getErrorMessage(error),
            })}
          />
        )}

        {error && !isDocumentLimitError(error) && (
          <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2">
            {getErrorMessage(error)}
          </p>
        )}

        <div className="flex gap-4 pt-2">
          <button
            type="submit"
            disabled={loading || importBusy}
            className="px-8 py-2 bg-amendly-blue text-white rounded-md font-body text-body-md disabled:opacity-50"
          >
            {loading ? t('org.creating') : t('org.create_document')}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={loading || importBusy}
            className="px-8 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md"
          >
            {t('org.cancel')}
          </button>
        </div>

        {/* Body — rich text editor + import buttons */}
        <div>
          <label className="font-body text-label-sm text-on-surface tracking-[0.02em] uppercase">
            {t('org.doc_body_label')} <span className="text-outline">{t('org.doc_body_optional')}</span>
          </label>
          <p className="mt-1 font-body text-label-sm text-outline">
            {t('document.body_section_hint')}
          </p>
          <p className="mt-0.5 font-body text-label-sm text-outline">
            {t('document.body_open_lock_hint')}
          </p>

          <div className="mt-4">
            <DocumentImportWorkflow
              slug={slug}
              currentTitle={title}
              currentBody={body}
              onBusyChange={setImportBusy}
              t={t}
              onApplyImport={({ body: importedBody, suggestedTitle, summary }) => {
                const finalBody =
                  summary.headingCount === 0
                    ? autoProposeSectionsFromParagraphs(importedBody)
                    : importedBody
                setBody(finalBody)
                setTitle((current) => current.trim() || suggestedTitle)
                setImportKey((value) => value + 1)
              }}
            />
          </div>

          <div className="relative mt-4">
            <RichTextEditor
              key={importKey}
              value={body}
              onChange={setBody}
              placeholder={t('org.doc_body_placeholder')}
              minHeight="min-h-[240px]"
              maxHeight="max-h-[480px] overflow-y-auto"
            />
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowStructurer((value) => !value)}
              className="font-body text-label-sm text-secondary hover:underline"
            >
              {showStructurer ? t('document.structurer_hide') : t('document.structurer_show')}
            </button>
          </div>

          {showStructurer && (
            <DocumentStructurer body={body} onChange={setBody} t={t} />
          )}
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Role badge
// ---------------------------------------------------------------------------

/**
 * Soft-fill badge showing a member's role within an organisation.
 *
 * Uses the Editorial Ledger status badge tokens:
 *   owner  → primary-fixed (like "open")
 *   admin  → tertiary-fixed (like "closed")
 *   member → surface-container-highest (like "draft")
 *
 * @param {{ role: 'owner' | 'admin' | 'member'; label: string }} props
 */
function RoleBadge({ role, label }) {
  const styles = {
    owner:  'bg-primary-fixed text-on-primary-fixed',
    admin:  'bg-tertiary-fixed text-on-tertiary-fixed',
    member: 'bg-surface-container-highest text-on-surface',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md font-body text-label-sm tracking-[0.02em] uppercase ${styles[role] ?? styles.member}`}
    >
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Avatar initials
// ---------------------------------------------------------------------------

/**
 * Circular avatar showing the member's initials or first letter of email.
 *
 * @param {{ name: string | null; email: string }} props
 */
function AvatarInitials({ name, email }) {
  const initials = name
    ? name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
    : email[0].toUpperCase()
  return (
    <span
      aria-hidden="true"
      className="flex-shrink-0 w-9 h-9 rounded-full bg-surface-container-highest text-on-surface flex items-center justify-center font-body text-label-sm tracking-[0.02em] font-semibold select-none"
    >
      {initials}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Members panel (collapsible)
// ---------------------------------------------------------------------------

/**
 * Panel listing all members of an organisation.
 *
 * Visible to all org members. Owner/admin sees a role selector, a remove button
 * per member row, and a "Pending invitations" sub-section with Revoke/Resend
 * actions per pending invite. Non-owner members see a "Leave organisation" button
 * on their own row.
 *
 * Props:
 *   slug            — Organisation slug.
 *   userRole        — The current user's role ('owner' | 'admin' | 'member').
 *   orgPlan         — The organisation's billing plan ('solo' | 'team' | 'organisation').
 *   currentUserId   — The current user's ID (to distinguish own row).
 *   alwaysOpen      — When true, renders content immediately without a toggle.
 *   onMemberRemoved — Called after another member is successfully removed (e.g. to update parent stats).
 *   onSelfLeft      — Called after the current user leaves the organisation (navigate away).
 *   t               — Translation function from useTranslation.
 */
function MembersPanel({ slug, userRole, orgPlan = 'solo', currentUserId, alwaysOpen = false, onMemberRemoved, onSelfLeft, t }) {
  const [open, setOpen] = useState(false)
  const [members, setMembers] = useState([])
  const [invitations, setInvitations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pendingRole, setPendingRole] = useState({})    // { userId: bool }
  const [pendingRemove, setPendingRemove] = useState({}) // { userId: bool }
  const [pendingRevoke, setPendingRevoke] = useState({}) // { invId: bool }
  const [pendingResend, setPendingResend] = useState({}) // { invId: bool }

  const canManage = userRole === 'owner' || userRole === 'admin'

  async function loadMembers() {
    setLoading(true)
    setError(null)
    try {
      const [membersData, invData] = await Promise.all([
        orgClient.listMembers(slug),
        canManage ? orgClient.listInvitations(slug) : Promise.resolve([]),
      ])
      setMembers(membersData)
      setInvitations(invData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // When alwaysOpen, load members on mount
  useEffect(() => {
    if (alwaysOpen) loadMembers()
  }, [alwaysOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleToggle() {
    if (!open && members.length === 0) {
      loadMembers()
    }
    setOpen((o) => !o)
  }

  const isExpanded = alwaysOpen || open

  async function handleRoleChange(userId, newRole) {
    setPendingRole((p) => ({ ...p, [userId]: true }))
    try {
      const updated = await orgClient.changeMemberRole(slug, userId, newRole)
      setMembers((prev) =>
        prev.map((m) => (m.user_id === userId ? { ...m, role: updated.role } : m))
      )
    } catch {
      setError(t('org.role_change_error'))
    } finally {
      setPendingRole((p) => ({ ...p, [userId]: false }))
    }
  }

  async function handleRemove(userId, displayName) {
    const confirmed = window.confirm(
      t('org.confirm_remove').replace('{name}', displayName)
    )
    if (!confirmed) return
    setPendingRemove((p) => ({ ...p, [userId]: true }))
    try {
      await orgClient.removeMember(slug, userId)
      setMembers((prev) => prev.filter((m) => m.user_id !== userId))
      onMemberRemoved?.()
    } catch {
      setError(t('org.remove_error'))
    } finally {
      setPendingRemove((p) => ({ ...p, [userId]: false }))
    }
  }

  async function handleLeave() {
    const confirmed = window.confirm(t('org.confirm_leave'))
    if (!confirmed) return
    setPendingRemove((p) => ({ ...p, [currentUserId]: true }))
    try {
      await orgClient.removeMember(slug, currentUserId)
      onSelfLeft?.()
    } catch {
      setError(t('org.leave_error'))
      setPendingRemove((p) => ({ ...p, [currentUserId]: false }))
    }
  }

  async function handleRevoke(invId, email) {
    const confirmed = window.confirm(
      t('org.confirm_revoke').replace('{email}', email)
    )
    if (!confirmed) return
    setPendingRevoke((p) => ({ ...p, [invId]: true }))
    try {
      await orgClient.revokeInvitation(slug, invId)
      setInvitations((prev) => prev.filter((inv) => inv.id !== invId))
    } catch {
      setError(t('org.revoke_error'))
    } finally {
      setPendingRevoke((p) => ({ ...p, [invId]: false }))
    }
  }

  async function handleResend(invId) {
    setPendingResend((p) => ({ ...p, [invId]: true }))
    try {
      const updated = await orgClient.resendInvitation(slug, invId)
      setInvitations((prev) =>
        prev.map((inv) => (inv.id === invId ? updated : inv))
      )
    } catch {
      setError(t('org.resend_error'))
    } finally {
      setPendingResend((p) => ({ ...p, [invId]: false }))
    }
  }

  const roleLabel = {
    owner:  t('org.role_owner'),
    admin:  t('org.role_admin'),
    member: t('org.role_member'),
  }

  return (
    <section className={alwaysOpen ? '' : 'mt-16'}>
      {/* Section header with toggle — hidden when alwaysOpen (tab renders its own heading) */}
      {!alwaysOpen && (
        <div className="flex items-center justify-between mb-8">
          <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
            {t('org.members_section')}
            {members.length > 0 && (
              <span className="ml-2 font-body text-body-md text-outline">({members.length})</span>
            )}
          </h2>
          <button
            type="button"
            onClick={handleToggle}
            className="font-body text-body-md text-secondary hover:underline"
          >
            {open ? t('org.members_toggle_hide') : t('org.members_toggle_show')}
          </button>
        </div>
      )}

      {isExpanded && (
        <>
          {loading && (
            <p className="font-body text-body-md text-outline">{t('common.loading')}</p>
          )}

          {error && (
            <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-4">
              {error}
            </p>
          )}

          {!loading && members.length > 0 && (
            <div className="space-y-3">
              {members.map((member) => {
                const memberId = member.user_id ?? member.id ?? null
                const memberName = member.name ?? member.full_name ?? null
                const displayName = memberName || member.email
                const isSelf = memberId === currentUserId
                const isOwner = member.role === 'owner'

                return (
                  <div
                    key={memberId ?? member.email}
                    className="bg-surface-container-lowest rounded-md shadow-ambient px-6 py-4 flex items-center gap-4"
                  >
                    {/* Avatar */}
                    <AvatarInitials name={memberName} email={member.email} />

                    {/* Name + email */}
                    <div className="flex-1 min-w-0">
                      <p className="font-body text-body-md text-on-surface truncate">
                        {memberName ?? member.email}
                      </p>
                      {memberName && (
                        <p className="font-body text-label-sm text-outline truncate">
                          {member.email}
                        </p>
                      )}
                      {/* Last activity date — owner only, paid plan only */}
                      {userRole === 'owner' && orgPlan !== 'solo' && (
                        <p className="font-body text-label-sm text-outline mt-0.5">
                          {member.last_activity_at
                            ? t('org.member_last_active').replace(
                                '{date}',
                                new Date(member.last_activity_at).toLocaleDateString()
                              )
                            : t('org.member_no_activity')}
                        </p>
                      )}
                    </div>

                    {/* Role badge (read-only for non-owners, or for the owner row itself) */}
                    {(userRole !== 'owner' || isOwner || isSelf) ? (
                      <RoleBadge role={member.role} label={roleLabel[member.role] ?? member.role} />
                    ) : (
                      /* Role selector — owner only, for non-owner rows that aren't self */
                      <select
                        value={member.role}
                        disabled={!memberId || pendingRole[memberId]}
                        onChange={(e) => memberId && handleRoleChange(memberId, e.target.value)}
                        className="bg-surface-container-highest text-on-surface font-body text-body-md rounded-md px-3 py-1 focus:outline-none focus:ring-2 focus:ring-secondary disabled:opacity-50"
                      >
                        <option value="admin">{t('org.role_admin')}</option>
                        <option value="member">{t('org.role_member')}</option>
                      </select>
                    )}

                    {/* Remove button — owner/admin, not for owner row, not for self */}
                    {canManage && !isOwner && !isSelf && (
                      <button
                        type="button"
                        disabled={!memberId || pendingRemove[memberId]}
                        onClick={() => memberId && handleRemove(memberId, displayName)}
                        className="flex-shrink-0 px-4 py-1 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-error-container/40 hover:text-on-error-container transition-colors disabled:opacity-50"
                      >
                        {pendingRemove[memberId]
                          ? t('org.removing')
                          : t('org.remove_member')}
                      </button>
                    )}

                    {/* Leave button — current user's own row, non-owner only */}
                    {isSelf && !isOwner && (
                      <button
                        type="button"
                        disabled={pendingRemove[currentUserId]}
                        onClick={handleLeave}
                        className="flex-shrink-0 px-4 py-1 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-error-container/40 hover:text-on-error-container transition-colors disabled:opacity-50"
                      >
                        {pendingRemove[currentUserId]
                          ? t('org.leaving')
                          : t('org.leave_org')}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Pending invitations — owner/admin only */}
          {!loading && canManage && invitations.length > 0 && (
            <div className="mt-10">
              <h3 className="font-body text-label-sm text-outline tracking-[0.08em] uppercase mb-4">
                {t('org.pending_invitations')}
                <span className="ml-2">({invitations.length})</span>
              </h3>
              <div className="space-y-2">
                {invitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="bg-surface-container-lowest rounded-md shadow-ambient px-6 py-3 flex items-center gap-4"
                  >
                    {/* Envelope icon placeholder */}
                    <span
                      aria-hidden="true"
                      className="flex-shrink-0 w-9 h-9 rounded-full bg-surface-container-highest text-outline flex items-center justify-center font-body text-label-sm select-none"
                    >
                      ✉
                    </span>

                    {/* Email + expiry */}
                    <div className="flex-1 min-w-0">
                      <p className="font-body text-body-md text-on-surface truncate">
                        {inv.email}
                      </p>
                      <p className="font-body text-label-sm text-outline">
                        {t('org.invitation_expires').replace(
                          '{date}',
                          new Date(inv.expires_at).toLocaleDateString()
                        )}
                      </p>
                    </div>

                    {/* Resend button */}
                    <button
                      type="button"
                      disabled={pendingResend[inv.id]}
                      onClick={() => handleResend(inv.id)}
                      className="flex-shrink-0 px-4 py-1 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-primary-fixed hover:text-on-primary-fixed transition-colors disabled:opacity-50"
                    >
                      {pendingResend[inv.id] ? t('org.resending') : t('org.resend_invitation')}
                    </button>

                    {/* Revoke button */}
                    <button
                      type="button"
                      disabled={pendingRevoke[inv.id]}
                      onClick={() => handleRevoke(inv.id, inv.email)}
                      className="flex-shrink-0 px-4 py-1 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-error-container/40 hover:text-on-error-container transition-colors disabled:opacity-50"
                    >
                      {pendingRevoke[inv.id] ? t('org.revoking') : t('org.revoke_invitation')}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Activity feed (collapsible)
// ---------------------------------------------------------------------------

/**
 * Relative time formatter — returns a localised "X minutes/hours/days ago"
 * string using the "time.*" i18n keys.
 *
 * @param {string} isoString - ISO-8601 UTC date string from the API.
 * @param {Function} t - Translation function from useTranslation.
 * @returns {string} Human-readable relative time string.
 */
/**
 * Collapsible "Recent activity" panel displayed at the bottom of OrgDetail,
 * below the Members panel.
 *
 * Fetches data lazily — the first expand triggers page 1 of
 * GET /api/organisations/{slug}/activity.  A "Load more" button appends
 * subsequent pages without replacing existing entries.
 *
 * Props:
 *   slug — Organisation slug.
 *   t    — Translation function from useTranslation.
 */
function ActivityFeed({ slug, userRole, t }) {
  const [open, setOpen] = useState(false)
  const [entries, setEntries] = useState([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  const canManage = userRole === 'owner' || userRole === 'admin'

  async function handleExport() {
    setExporting(true)
    try {
      await orgClient.exportActivity(slug)
    } catch {
      // Silently ignore — the download failing is non-critical
    } finally {
      setExporting(false)
    }
  }

  const hasMore = entries.length < total

  async function loadActivity(pageNum = 1, append = false) {
    if (append) {
      setLoadingMore(true)
    } else {
      setLoading(true)
    }
    setError(null)
    try {
      const data = await orgClient.getActivity(slug, pageNum)
      if (append) {
        setEntries((prev) => [...prev, ...data.items])
      } else {
        setEntries(data.items)
      }
      setTotal(data.total)
      setPage(pageNum)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  function handleToggle() {
    if (!open && entries.length === 0) {
      loadActivity(1, false)
    }
    setOpen((o) => !o)
  }

  function handleLoadMore() {
    loadActivity(page + 1, true)
  }

  /**
   * Build the human-readable sentence for one activity entry.
   * Pattern: "{actor} {verb} {doc_title}"
   */
  function entryLabel(entry) {
    const verb = t(`activity.${entry.action}`) || entry.action.replace(/_/g, ' ')
    if (entry.doc_title) {
      return `${entry.actor_name} ${verb} ${entry.doc_title}`
    }
    return `${entry.actor_name} ${verb}`
  }

  return (
    <section className="mt-16">
      {/* Section header with toggle */}
      <div className="flex items-center justify-between mb-8">
        <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('activity.section_title')}
          {total > 0 && (
            <span className="ml-2 font-body text-body-md text-outline">({total})</span>
          )}
        </h2>
        <div className="flex items-center gap-3">
          {canManage && (
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="font-body text-label-sm text-outline hover:text-on-surface px-3 py-1 rounded-md bg-surface-container-highest hover:bg-surface-container transition-colors disabled:opacity-50"
            >
              {exporting ? t('common.loading') : t('activity.export')}
            </button>
          )}
          <button
            type="button"
            onClick={handleToggle}
            className="font-body text-body-md text-secondary hover:underline"
          >
            {open ? t('activity.toggle_hide') : t('activity.toggle_show')}
          </button>
        </div>
      </div>

      {open && (
        <>
          {loading && (
            <p className="font-body text-body-md text-outline">{t('common.loading')}</p>
          )}

          {error && (
            <p className="font-body text-body-md text-on-error-container bg-error-container/40 rounded-md px-4 py-2 mb-4">
              {error}
            </p>
          )}

          {!loading && entries.length === 0 && !error && (
            <p className="font-body text-body-md text-outline">{t('activity.no_entries')}</p>
          )}

          {!loading && entries.length > 0 && (
            <>
              <div className="space-y-3">
                {entries.map((entry) => (
                  <div
                    key={entry.id}
                    className="bg-surface-container-lowest rounded-md shadow-ambient px-6 py-4 flex items-start gap-4"
                  >
                    {/* Icon */}
                    <span
                      aria-hidden="true"
                      className="flex-shrink-0 text-lg leading-none mt-0.5"
                    >
                      {ACTION_ICONS[entry.action] ?? '•'}
                    </span>

                    {/* Text */}
                    <div className="flex-1 min-w-0">
                      <p className="font-body text-body-md text-on-surface">
                        {entryLabel(entry)}
                      </p>
                      <p className="font-body text-label-sm text-outline mt-0.5">
                        {relativeTime(entry.created_at, t)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Load more button */}
              {hasMore && (
                <div className="mt-6 flex justify-center">
                  <button
                    type="button"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="px-8 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-50"
                  >
                    {loadingMore ? t('common.loading') : t('activity.load_more')}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Document row
// ---------------------------------------------------------------------------

/**
 * Single document row — clickable to navigate, or selectable via checkbox in selection mode.
 *
 * Props:
 *   doc           — Document object { id, title, status, created_at }.
 *   onClick       — Called when the row is clicked (navigation, only in normal mode).
 *   t             — Translation function from useTranslation.
 *   selectionMode — Boolean; if true, shows a checkbox instead of navigating.
 *   selected      — Boolean; whether this document is currently selected.
 *   onToggle      — Called with doc.id when the checkbox is toggled.
 */
function DocumentRow({ doc, onClick, t, selectionMode = false, selected = false, onToggle }) {
  const date = new Date(doc.created_at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

  if (selectionMode) {
    return (
      <label
        className={`w-full flex items-center gap-4 rounded-md shadow-ambient p-6 cursor-pointer transition-colors ${
          selected
            ? 'bg-primary-fixed text-on-primary-fixed'
            : 'bg-surface-container-lowest hover:bg-surface-container-low'
        }`}
      >
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(doc.id)}
          className="w-4 h-4 shrink-0 accent-amendly-blue"
        />
        <div className="flex-1 min-w-0 space-y-1">
          <h3 className="font-display text-title-sm text-on-surface truncate">{doc.title}</h3>
          <p className="font-body text-label-sm text-outline tracking-[0.02em]">{date}</p>
        </div>
        <StatusBadge status={doc.status} t={t} />
      </label>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left bg-surface-container-lowest rounded-md shadow-ambient p-6 flex items-center justify-between hover:bg-surface-container-low transition-colors"
    >
      <div className="space-y-1">
        <h3 className="font-display text-title-sm text-on-surface">{doc.title}</h3>
        <p className="font-body text-label-sm text-outline tracking-[0.02em]">{date}</p>
      </div>
      <StatusBadge status={doc.status} t={t} />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Batch delete confirmation modal
// ---------------------------------------------------------------------------

/**
 * Modal dialog requiring the user to type "DELETE" before confirming batch deletion.
 *
 * Props:
 *   count     — Number of documents selected for deletion.
 *   onConfirm — Called when the user has typed DELETE and clicked the confirm button.
 *   onCancel  — Called when the user closes/cancels the modal.
 *   loading   — Boolean; disables inputs while the delete request is in flight.
 *   error     — Error message string to display, or null.
 *   t         — Translation function from useTranslation.
 */
function DeleteDocumentsModal({ count, onConfirm, onCancel, loading, error, t }) {
  const [confirmText, setConfirmText] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    const id = window.requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }))
    return () => window.cancelAnimationFrame(id)
  }, [])

  function handleKeyDown(e) {
    if (e.key === 'Escape' && !loading) onCancel()
  }

  const canConfirm = confirmText === 'DELETE' && !loading

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onKeyDown={handleKeyDown}
    >
      <div className="bg-surface-container-lowest rounded-lg shadow-ambient w-full max-w-md p-8 space-y-6">
        <h2 className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {t('org.delete_docs_modal_title').replace('{n}', count)}
        </h2>
        <p className="font-body text-body-md text-outline">
          {t('org.delete_docs_modal_body')}
        </p>
        <div>
          <input
            ref={inputRef}
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={t('org.delete_docs_confirm_placeholder')}
            disabled={loading}
            className="w-full bg-surface-container-low rounded-md px-4 py-2 font-body text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-secondary disabled:opacity-50"
          />
        </div>
        {error && (
          <p className="font-body text-label-sm text-on-error-container">{error}</p>
        )}
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="px-6 py-2 bg-surface-container-highest text-on-surface rounded-md font-body text-body-md hover:bg-surface-container transition-colors disabled:opacity-50"
          >
            {t('org.cancel_selection')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={!canConfirm}
            className="px-6 py-2 bg-on-error-container text-white rounded-md font-body text-body-md transition-colors disabled:opacity-40 enabled:hover:opacity-90"
          >
            {loading ? t('org.deleting_docs') : t('org.delete_docs_confirm_button')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// OrgDetail page
// ---------------------------------------------------------------------------

/**
 * OrgDetail page component.
 * Protected — ProtectedRoute ensures the user is authenticated before rendering.
 */
export default function OrgDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { t, lang, setLang } = useTranslation()
  const currentUser = useAuthStore((s) => s.user)

  const [org, setOrg] = useState(null)
  const [userRole, setUserRole] = useState(null)   // 'owner' | 'admin' | 'member'
  const [documents, setDocuments] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState(null)  // { active_docs, pending_amendments, member_count }
  const [notificationsMuted, setNotificationsMuted] = useState(false)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('newest')  // 'newest' | 'oldest' | 'title_az' | 'title_za' | 'status'
  const [activeTab, setActiveTab] = useState('documents')  // 'documents' | 'members'
  const [pendingToast, setPendingToast] = useState(false)
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedDocIds, setSelectedDocIds] = useState(new Set())
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState(null)
  const docRowRefs = useRef({})
  const createFormTriggerRef = useRef(null)
  const inviteFormTriggerRef = useRef(null)

  const canManage = userRole === 'owner' || userRole === 'admin'
  const showSoloDocumentUpgrade = canManage && org?.plan === 'solo' && stats?.active_docs >= 3

  /**
   * Client-side filtered and sorted slice of the current page of documents.
   * Search matches on title (case-insensitive, leading/trailing whitespace ignored).
   * Sort operates on the filtered result.
   */
  const filteredDocuments = useFilteredDocuments(documents, search, sortBy)

  const PAGE_SIZE = 20
  const totalPages = Math.ceil(total / PAGE_SIZE)

  /**
   * Clicking the "N pending" stats badge switches to the documents tab (if needed)
   * and scrolls to the first document that has pending amendments on the current page.
   * If no such document exists, shows a brief informational toast.
   *
   * Side effects:
   *   - May change activeTab to 'documents'.
   *   - May set pendingToast (auto-cleared after 3 s).
   */
  function handlePendingStatClick() {
    setActiveTab('documents')
    const firstPending = documents.find((d) => (d.pending_count ?? 0) > 0)
    if (firstPending && docRowRefs.current[firstPending.id]) {
      docRowRefs.current[firstPending.id].scrollIntoView({ behavior: 'smooth', block: 'center' })
      setPendingToast(false)
    } else {
      setPendingToast(true)
      setTimeout(() => setPendingToast(false), 3000)
    }
  }

  // -------------------------------------------------------------------------
  // Load org + documents
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [orgData, docsData, myOrgs, statsData, notifSettings] = await Promise.all([
          orgClient.getOrg(slug),
          orgClient.listDocuments(slug, page),
          orgClient.listMyOrgs(),
          orgClient.getOrgStats(slug),
          authFetch('/api/me/notifications/settings')
            .then((r) => (r.ok ? r.json() : null))
            .catch(() => null),
        ])
        if (!cancelled) {
          setOrg(orgData)
          setDocuments(docsData.items)
          setTotal(docsData.total)
          setStats(statsData)
          const membership = myOrgs.find((o) => o.slug === slug)
          setUserRole(membership?.role ?? 'member')
          const orgNotifState = notifSettings?.orgs?.find((o) => o.slug === slug)
          setNotificationsMuted(orgNotifState?.notifications_muted ?? false)
        }
      } catch (err) {
        if (!cancelled) {
          if (err.message?.includes('404') || err.message?.toLowerCase().includes('not found')) {
            navigate('/dashboard', { replace: true })
          } else {
            setError(err.message)
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [slug, page]) // eslint-disable-line react-hooks/exhaustive-deps

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  /**
   * Called by CreateDocumentForm after a successful POST.
   *
   * Navigates directly to the newly created document so the user can
   * immediately see and work on it — especially important after PDF/DOCX import
   * where the document already has content.
   *
   * @param {Object} doc - The newly created document returned by the API.
   */
  function handleDocCreated(doc) {
    navigate(`/orgs/${slug}/documents/${doc.id}`)
  }

  function toggleDocSelection(docId) {
    setSelectedDocIds((prev) => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  function handleSelectAll() {
    if (selectedDocIds.size === filteredDocuments.length) {
      setSelectedDocIds(new Set())
    } else {
      setSelectedDocIds(new Set(filteredDocuments.map((d) => d.id)))
    }
  }

  function exitSelectionMode() {
    setSelectionMode(false)
    setSelectedDocIds(new Set())
    setDeleteError(null)
  }

  async function handleDeleteConfirm() {
    setDeleteLoading(true)
    setDeleteError(null)
    try {
      await orgClient.deleteDocuments(slug, Array.from(selectedDocIds))
      setDocuments((prev) => prev.filter((d) => !selectedDocIds.has(d.id)))
      setTotal((prev) => prev - selectedDocIds.size)
      setShowDeleteModal(false)
      exitSelectionMode()
      // Refresh stats
      orgClient.getOrgStats(slug).then(setStats).catch(() => {})
    } catch (err) {
      setDeleteError(t('org.delete_docs_error'))
    } finally {
      setDeleteLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="font-body text-body-md text-outline">{t('common.loading')}</span>
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
      {/* ------------------------------------------------------------------ */}
      {/* Top navigation bar                                                  */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface-container-low px-8 py-4 flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="font-body text-body-md text-secondary hover:underline"
        >
          {t('nav.back_dashboard')}
        </button>
        <span className="font-body text-body-md text-outline">/</span>
        <span className="font-display text-headline-sm text-on-surface tracking-[-0.01em]">
          {org?.name}
        </span>
        <PlanBadge plan={org?.plan ?? 'free'} />
        {/* Owner-only header actions: Billing + Settings */}
        {userRole === 'owner' && (
          <div className="ml-auto flex items-center gap-4">
            <button
              type="button"
              onClick={() => navigate(`/orgs/${slug}/billing`)}
              className="font-body text-body-md text-secondary hover:underline"
            >
              {t('nav.billing')}
            </button>
            <button
              type="button"
              onClick={() => navigate(`/orgs/${slug}/settings`)}
              className="font-body text-body-md text-secondary hover:underline"
            >
              {t('nav.org_settings')}
            </button>
          </div>
        )}

        {/* Notification center */}
        <NotificationBell orgSlug={slug} />

        {/* Language switcher — rightmost */}
        <LanguageSwitcher lang={lang} setLang={setLang} />
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-3xl mx-auto px-8 py-12">
        {/* Page headline */}
        <OrgDetailHero
          org={org}
          stats={stats}
          notificationsMuted={notificationsMuted}
          pendingToast={pendingToast}
          t={t}
          onPendingStatClick={handlePendingStatClick}
        />

        <OrgDetailTabs
          activeTab={activeTab}
          t={t}
          onChange={(tabId) => {
            setActiveTab(tabId)
            if (tabId !== 'documents') {
              setShowCreateForm(false)
              setShowInviteForm(false)
              exitSelectionMode()
            }
          }}
        />

        {activeTab === 'members' && (
          <MembersTabSection
            canManage={canManage}
            showInviteForm={showInviteForm}
            slug={slug}
            userRole={userRole}
            orgPlan={org?.plan ?? 'solo'}
            currentUserId={currentUser?.id ?? null}
            inviteFormTriggerRef={inviteFormTriggerRef}
            InviteMemberForm={InviteMemberForm}
            MembersPanel={MembersPanel}
            navigate={navigate}
            setShowInviteForm={setShowInviteForm}
            setStats={setStats}
            restoreTriggerFocus={restoreTriggerFocus}
            t={t}
          />
        )}

        {activeTab === 'documents' && (
          <>
            <DocumentsTabSection
              documents={documents}
              filteredDocuments={filteredDocuments}
              totalPages={totalPages}
              userRole={userRole}
              canManage={canManage}
              showCreateForm={showCreateForm}
              selectionMode={selectionMode}
              selectedDocIds={selectedDocIds}
              showSoloDocumentUpgrade={showSoloDocumentUpgrade}
              slug={slug}
              page={page}
              search={search}
              sortBy={sortBy}
              createFormTriggerRef={createFormTriggerRef}
              docRowRefs={docRowRefs}
              CreateDocumentForm={CreateDocumentForm}
              DocumentRow={DocumentRow}
              navigate={navigate}
              onCreateDocument={handleDocCreated}
              onShowCreateForm={() => setShowCreateForm(true)}
              onCancelCreate={() => {
                setShowCreateForm(false)
                restoreTriggerFocus(createFormTriggerRef)
              }}
              onSearchChange={setSearch}
              onSortChange={setSortBy}
              onToggleSelectionMode={() => setSelectionMode(true)}
              onSelectAll={handleSelectAll}
              onOpenDeleteModal={() => {
                setDeleteError(null)
                setShowDeleteModal(true)
              }}
              onExitSelectionMode={exitSelectionMode}
              onToggleDocSelection={toggleDocSelection}
              onPrevPage={() => setPage((currentPage) => currentPage - 1)}
              onNextPage={() => setPage((currentPage) => currentPage + 1)}
              t={t}
            />

            <ActivityFeed slug={slug} userRole={userRole} t={t} />
          </>
        )}
      </main>

      {showDeleteModal && (
        <DeleteDocumentsModal
          count={selectedDocIds.size}
          onConfirm={handleDeleteConfirm}
          onCancel={() => { setShowDeleteModal(false); setDeleteError(null) }}
          loading={deleteLoading}
          error={deleteError}
          t={t}
        />
      )}
    </div>
  )
}
