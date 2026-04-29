export function getUpgradeHref(userRole, slug) {
  return userRole === 'owner' ? `/orgs/${slug}/billing` : '/pricing'
}

export function getDocumentUpgradeCallout({ t, userRole, slug, note = null }) {
  return {
    title: t('org.upgrade_docs_title'),
    body: t(userRole === 'owner' ? 'org.upgrade_docs_body_owner' : 'org.upgrade_docs_body_member'),
    benefits: [
      t('org.upgrade_docs_benefit_1'),
      t('org.upgrade_docs_benefit_2'),
      t('org.upgrade_docs_benefit_3'),
    ],
    ctaLabel: t(userRole === 'owner' ? 'org.upgrade_cta_owner' : 'org.upgrade_cta_compare'),
    ctaTo: getUpgradeHref(userRole, slug),
    note: note ? t('org.upgrade_note').replace('{message}', note) : null,
  }
}

export function getSeatUpgradeCallout({ t, userRole, slug, note = null }) {
  return {
    title: t('org.upgrade_seats_title'),
    body: t(userRole === 'owner' ? 'org.upgrade_seats_body_owner' : 'org.upgrade_seats_body_member'),
    benefits: [
      t('org.upgrade_seats_benefit_1'),
      t('org.upgrade_seats_benefit_2'),
      t('org.upgrade_seats_benefit_3'),
    ],
    ctaLabel: t(userRole === 'owner' ? 'org.upgrade_cta_owner' : 'org.upgrade_cta_compare'),
    ctaTo: getUpgradeHref(userRole, slug),
    note: note ? t('org.upgrade_note').replace('{message}', note) : null,
  }
}

export function restoreTriggerFocus(triggerRef) {
  window.requestAnimationFrame(() => {
    triggerRef?.current?.focus?.({ preventScroll: true })
  })
}

export function relativeTime(isoString, t) {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return t('activity.just_now')
  if (diffMins < 60) return t('activity.minutes_ago').replace('{count}', diffMins)
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return t('activity.hours_ago').replace('{count}', diffHours)
  const diffDays = Math.floor(diffHours / 24)
  return t('activity.days_ago').replace('{count}', diffDays)
}

export const ACTION_ICONS = {
  document_created: '📄',
  status_changed: '🔄',
  amendment_submitted: '✍️',
  amendment_status_changed: '✅',
  amendment_withdrawn: '↩️',
  member_joined: '👥',
  member_removed: '➖',
}
