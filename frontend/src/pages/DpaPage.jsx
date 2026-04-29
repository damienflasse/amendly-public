/**
 * DpaPage — static Data Processing Agreement page at "/legal/dpa".
 *
 * Publicly accessible (no auth required). Content is fully localised via the
 * "legal" namespace across all four i18n JSON files.
 *
 * Design follows "The Editorial Ledger" (frontend/DESIGN.md).
 *
 * Props: none
 */

import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'

function Section({ title, body }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-display text-headline-sm text-amendly-dark">{title}</h2>
      <p className="font-body text-body-md text-amendly-dark leading-relaxed">{body}</p>
    </section>
  )
}

export default function DpaPage() {
  const { t, lang } = useTranslation()

  useSeoMeta({
    title: 'Data Processing Agreement — Amendly',
    description: 'Amendly Data Processing Agreement (DPA) — obligations of Amendly as a data processor under Article 28 GDPR.',
    canonical: 'https://amendly.eu/legal/dpa',
    lang: lang || 'en',
  })

  const sections = [
    { title: t('legal.dpa_s1_title'), body: t('legal.dpa_s1_body') },
    { title: t('legal.dpa_s2_title'), body: t('legal.dpa_s2_body') },
    { title: t('legal.dpa_s3_title'), body: t('legal.dpa_s3_body') },
    { title: t('legal.dpa_s4_title'), body: t('legal.dpa_s4_body') },
    { title: t('legal.dpa_s5_title'), body: t('legal.dpa_s5_body') },
    { title: t('legal.dpa_s6_title'), body: t('legal.dpa_s6_body') },
    { title: t('legal.dpa_s7_title'), body: t('legal.dpa_s7_body') },
    { title: t('legal.dpa_s8_title'), body: t('legal.dpa_s8_body') },
    { title: t('legal.dpa_s9_title'), body: t('legal.dpa_s9_body') },
    { title: t('legal.dpa_contact_title'), body: t('legal.dpa_contact_body') },
  ]

  return (
    <div className="min-h-screen bg-amendly-light">
      <PublicHeader />

      <main className="max-w-3xl mx-auto px-8 py-12 flex flex-col gap-12">
        <div className="flex flex-col gap-4">
          <Link
            to="/"
            className="font-body text-body-md text-amendly-gray hover:text-amendly-blue transition-colors"
          >
            {t('legal.back_home')}
          </Link>
          <h1 className="font-display text-display-md text-amendly-dark">
            {t('legal.dpa_title')}
          </h1>
          <p className="font-body text-body-md text-amendly-gray">{t('legal.dpa_last_updated')}</p>
          <p className="font-body text-body-md text-amendly-dark leading-relaxed">
            {t('legal.dpa_intro')}
          </p>
        </div>

        {sections.map((s) => (
          <Section key={s.title} title={s.title} body={s.body} />
        ))}
      </main>

      <PublicFooter />
    </div>
  )
}
