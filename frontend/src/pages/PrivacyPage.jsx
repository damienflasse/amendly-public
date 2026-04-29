/**
 * PrivacyPage — static Privacy Policy page at "/legal/privacy".
 *
 * Publicly accessible (no auth required). Content is fully localised via the
 * "legal" namespace across all four i18n JSON files.
 *
 * Design follows "The Editorial Ledger" (frontend/DESIGN.md):
 *   - Manrope for the page title (headline-sm), Inter for all prose
 *   - Tonal background shifts — no 1px borders for layout separation
 *   - Prose sections separated by vertical whitespace, not dividers
 *   - Narrow readable column, centred on the page
 *
 * Props: none
 */

import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import LanguageSwitcher from '../components/LanguageSwitcher'

/**
 * A single prose section with a headline-sm title and body paragraph.
 *
 * @param {{ title: string, body: string }} props
 */
function Section({ title, body }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-display text-headline-sm text-amendly-dark">{title}</h2>
      <p className="font-body text-body-md text-amendly-dark leading-relaxed">{body}</p>
    </section>
  )
}

export default function PrivacyPage() {
  const { t, lang } = useTranslation()

  useSeoMeta({
    title: 'Privacy Policy — Amendly',
    description: 'Amendly Privacy Policy — how we collect, use, and protect your personal data under GDPR.',
    canonical: 'https://amendly.eu/legal/privacy',
    lang: lang || 'en',
  })

  const sections = [
    { title: t('legal.privacy_s1_title'), body: t('legal.privacy_s1_body') },
    { title: t('legal.privacy_s2_title'), body: t('legal.privacy_s2_body') },
    { title: t('legal.privacy_s3_title'), body: t('legal.privacy_s3_body') },
    { title: t('legal.privacy_s4_title'), body: t('legal.privacy_s4_body') },
    { title: t('legal.privacy_s5_title'), body: t('legal.privacy_s5_body') },
    { title: t('legal.privacy_s6_title'), body: t('legal.privacy_s6_body') },
    { title: t('legal.privacy_s7_title'), body: t('legal.privacy_s7_body') },
    { title: t('legal.privacy_s8_title'), body: t('legal.privacy_s8_body') },
    { title: t('legal.privacy_s9_title'), body: t('legal.privacy_s9_body') },
    { title: t('legal.privacy_s10_title'), body: t('legal.privacy_s10_body') },
    { title: t('legal.privacy_s11_title'), body: t('legal.privacy_s11_body') },
    { title: t('legal.privacy_s12_title'), body: t('legal.privacy_s12_body') },
    { title: t('legal.privacy_s13_title'), body: t('legal.privacy_s13_body') },
    { title: t('legal.privacy_contact_title'), body: t('legal.privacy_contact_body') },
  ]

  return (
    <div className="min-h-screen bg-amendly-light">
      {/* Minimal nav */}
      <PublicHeader />

      {/* Content */}
      <main className="max-w-3xl mx-auto px-8 py-12 flex flex-col gap-12">
        {/* Page header */}
        <div className="flex flex-col gap-4">
          <Link
            to="/"
            className="font-body text-body-md text-amendly-gray hover:text-amendly-blue transition-colors"
          >
            {t('legal.back_home')}
          </Link>
          <h1 className="font-display text-display-md text-amendly-dark">
            {t('legal.privacy_title')}
          </h1>
          <p className="font-body text-body-md text-amendly-gray">{t('legal.last_updated')}</p>
          <p className="font-body text-body-md text-amendly-dark leading-relaxed">
            {t('legal.privacy_intro')}
          </p>
        </div>

        {/* Prose sections */}
        {sections.map((s) => (
          <Section key={s.title} title={s.title} body={s.body} />
        ))}
      </main>

      {/* Footer */}
      <PublicFooter />
    </div>
  )
}
