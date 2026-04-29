/**
 * HelpPage — public help centre at /help.
 *
 * Sections:
 *   1. Hero with search bar (decorative)
 *   2. Quick-action cards (Contact Support / Documentation)
 *   3. Getting-started guide (3 numbered steps with SVG mockup illustrations)
 *   4. Key-features explained (4 feature cards with inline SVG illustrations)
 *   5. FAQ accordion (5 items)
 *   6. Support CTA banner
 *
 * Props: none
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import JsonLd from '../components/JsonLd'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { Search, ChevronDown, BookOpen, MessageCircle, CheckCircle, FileText, Users, Download, Activity } from 'lucide-react'

// ---------------------------------------------------------------------------
// Inline SVG mockup illustrations
// ---------------------------------------------------------------------------

/** Mockup: organisation dashboard card list */
function IllustrationOrg() {
  return (
    <svg viewBox="0 0 320 200" className="w-full h-full" aria-hidden="true">
      <rect width="320" height="200" rx="12" fill="#f0f4ff" />
      {/* Header bar */}
      <rect x="0" y="0" width="320" height="40" rx="12" fill="#1a4bd4" />
      <rect x="12" y="13" width="60" height="14" rx="4" fill="rgba(255,255,255,0.9)" />
      <circle cx="294" cy="20" r="10" fill="rgba(255,255,255,0.3)" />
      {/* Org card 1 */}
      <rect x="12" y="56" width="296" height="44" rx="8" fill="white" />
      <rect x="24" y="66" width="80" height="10" rx="3" fill="#1a2d5a" />
      <rect x="24" y="80" width="110" height="7" rx="2" fill="#a0aec0" />
      <rect x="256" y="63" width="40" height="18" rx="9" fill="#dbe1ff" />
      <rect x="262" y="68" width="28" height="8" rx="2" fill="#003798" />
      {/* Org card 2 */}
      <rect x="12" y="108" width="296" height="44" rx="8" fill="white" />
      <rect x="24" y="118" width="100" height="10" rx="3" fill="#1a2d5a" />
      <rect x="24" y="132" width="90" height="7" rx="2" fill="#a0aec0" />
      <rect x="252" y="115" width="48" height="18" rx="9" fill="#e8f5e9" />
      <rect x="258" y="120" width="36" height="8" rx="2" fill="#2e7d32" />
      {/* Button */}
      <rect x="12" y="162" width="130" height="28" rx="6" fill="#1a4bd4" />
      <rect x="28" y="170" width="98" height="10" rx="3" fill="white" />
    </svg>
  )
}

/** Mockup: document with status badge + amendment form */
function IllustrationDocument() {
  return (
    <svg viewBox="0 0 320 200" className="w-full h-full" aria-hidden="true">
      <rect width="320" height="200" rx="12" fill="#f0f4ff" />
      {/* Doc title */}
      <rect x="12" y="14" width="160" height="14" rx="4" fill="#1a2d5a" />
      {/* Status badge */}
      <rect x="248" y="12" width="60" height="20" rx="10" fill="#d1fae5" />
      <rect x="258" y="17" width="40" height="10" rx="3" fill="#065f46" />
      {/* Body text lines */}
      <rect x="12" y="42" width="296" height="8" rx="2" fill="#cbd5e0" />
      <rect x="12" y="56" width="260" height="8" rx="2" fill="#cbd5e0" />
      <rect x="12" y="70" width="280" height="8" rx="2" fill="#cbd5e0" />
      <rect x="12" y="84" width="180" height="8" rx="2" fill="#cbd5e0" />
      {/* Divider */}
      <rect x="12" y="104" width="296" height="1" fill="#e2e8f0" />
      {/* Amendment form */}
      <rect x="12" y="114" width="130" height="12" rx="3" fill="#1a2d5a" />
      <rect x="12" y="132" width="296" height="28" rx="6" fill="white" />
      <rect x="20" y="140" width="120" height="10" rx="3" fill="#a0aec0" />
      <rect x="12" y="168" width="100" height="22" rx="5" fill="#1a4bd4" />
      <rect x="28" y="174" width="68" height="10" rx="3" fill="white" />
    </svg>
  )
}

/** Mockup: diff view with blue additions and strikethrough */
function IllustrationDiff() {
  return (
    <svg viewBox="0 0 320 200" className="w-full h-full" aria-hidden="true">
      <rect width="320" height="200" rx="12" fill="#f8f9ff" />
      {/* Header */}
      <rect x="12" y="12" width="100" height="12" rx="3" fill="#1a2d5a" />
      <rect x="244" y="10" width="64" height="20" rx="4" fill="#fff3cd" />
      <rect x="252" y="15" width="48" height="10" rx="2" fill="#856404" />
      {/* Original text block */}
      <rect x="12" y="38" width="60" height="10" rx="3" fill="#718096" />
      <rect x="12" y="54" width="296" height="8" rx="2" fill="#e2e8f0" />
      {/* strikethrough text block */}
      <rect x="12" y="68" width="200" height="8" rx="2" fill="#cbd5e0" />
      <rect x="12" y="71" width="200" height="2" fill="#717c82" />
      {/* Proposed block */}
      <rect x="12" y="90" width="80" height="10" rx="3" fill="#003798" />
      <rect x="12" y="106" width="296" height="8" rx="2" fill="#dbe1ff" />
      <rect x="12" y="120" width="240" height="8" rx="2" fill="#dbe1ff" />
      {/* Accept / Reject buttons */}
      <rect x="12" y="144" width="80" height="24" rx="5" fill="#d1fae5" />
      <rect x="24" y="150" width="56" height="12" rx="2" fill="#065f46" />
      <rect x="104" y="144" width="80" height="24" rx="5" fill="#fee2e2" />
      <rect x="116" y="150" width="56" height="12" rx="2" fill="#991b1b" />
      {/* Justification */}
      <rect x="12" y="178" width="150" height="8" rx="2" fill="#a0aec0" />
    </svg>
  )
}

/** Mockup: consolidated export panel */
function IllustrationExport() {
  return (
    <svg viewBox="0 0 320 200" className="w-full h-full" aria-hidden="true">
      <rect width="320" height="200" rx="12" fill="#f0f4ff" />
      {/* Panel header */}
      <rect x="12" y="12" width="140" height="14" rx="4" fill="#1a2d5a" />
      <rect x="220" y="10" width="88" height="22" rx="5" fill="#1a4bd4" />
      <rect x="232" y="15" width="64" height="12" rx="3" fill="white" />
      {/* Consolidated text lines */}
      <rect x="12" y="44" width="296" height="8" rx="2" fill="#cbd5e0" />
      <rect x="12" y="58" width="280" height="8" rx="2" fill="#dbe1ff" />
      <rect x="12" y="72" width="296" height="8" rx="2" fill="#cbd5e0" />
      <rect x="12" y="86" width="220" height="8" rx="2" fill="#dbe1ff" />
      <rect x="12" y="100" width="296" height="8" rx="2" fill="#cbd5e0" />
      {/* Export format row */}
      <rect x="12" y="126" width="88" height="30" rx="6" fill="white" />
      <rect x="22" y="133" width="68" height="16" rx="3" fill="#e2e8f0" />
      <rect x="108" y="126" width="88" height="30" rx="6" fill="white" />
      <rect x="118" y="133" width="68" height="16" rx="3" fill="#e2e8f0" />
      <rect x="204" y="126" width="88" height="30" rx="6" fill="white" />
      <rect x="214" y="133" width="68" height="16" rx="3" fill="#e2e8f0" />
      {/* Labels */}
      <rect x="24" y="136" width="40" height="10" rx="2" fill="#1a2d5a" />
      <rect x="120" y="136" width="40" height="10" rx="2" fill="#1a2d5a" />
      <rect x="216" y="136" width="40" height="10" rx="2" fill="#1a2d5a" />
      {/* Badge */}
      <rect x="12" y="168" width="180" height="20" rx="4" fill="#d1fae5" />
      <rect x="20" y="173" width="160" height="10" rx="2" fill="#065f46" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Feature card
// ---------------------------------------------------------------------------

/**
 * A feature explanation card with an icon, title, description, and SVG illustration.
 *
 * @param {{ icon: React.ReactNode, title: string, desc: string, illustration: React.ReactNode }} props
 */
function FeatureCard({ icon, title, desc, illustration }) {
  return (
    <div className="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
      <div className="h-44 bg-slate-50 p-4">
        {illustration}
      </div>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-blue-50 text-amendly-blue rounded-lg flex items-center justify-center shrink-0">
            {icon}
          </div>
          <h3 className="font-bold text-slate-900 text-lg">{title}</h3>
        </div>
        <p className="text-gray-500 text-sm leading-relaxed">{desc}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Getting-started step
// ---------------------------------------------------------------------------

/**
 * A numbered step in the "Getting started" guide.
 *
 * @param {{ number: number, title: string, desc: string, illustration: React.ReactNode }} props
 */
function GuideStep({ number, title, desc, illustration }) {
  return (
    <div className="flex flex-col md:flex-row items-start gap-8">
      <div className="md:w-1/2 space-y-4">
        <div className="flex items-center gap-4">
          <span className="w-10 h-10 rounded-full bg-amendly-blue text-white font-bold text-lg flex items-center justify-center shrink-0">
            {number}
          </span>
          <h3 className="text-xl font-bold text-slate-900">{title}</h3>
        </div>
        <p className="text-gray-500 leading-relaxed pl-14">{desc}</p>
      </div>
      <div className="md:w-1/2 h-44 w-full rounded-xl overflow-hidden bg-slate-50 border border-gray-100 shadow-sm">
        {illustration}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// HelpPage
// ---------------------------------------------------------------------------

const FAQ_EN = [
  {
    q: 'How do I create a new collaborative document?',
    a: "Simply log into your dashboard, click on 'Documents' in the sidebar, and use the 'New Document' button to either upload a .docx file or write one from scratch.",
  },
  {
    q: 'Can I invite external stakeholders to review?',
    a: 'Yes! You can share a secure review link with specific permissions. Guests will be able to submit amendments without needing full access to your organization workspace.',
  },
  {
    q: 'How does the consolidation feature work?',
    a: "Once your review period is over, the workspace owner or admin can review all submitted amendments. By clicking 'Accept' on an amendment, it automatically injects the diff into the final consolidation output. When done, you can export the clean version.",
  },
  {
    q: 'What formats are supported for export?',
    a: 'Currently, you can export your consolidated final text to PDF and standard Word (DOCX) formats.',
  },
  {
    q: 'Are my documents secure and private?',
    a: 'Absolutely. We use enterprise-grade encryption at rest and in transit. Your documents are strictly accessible only by the members you explicitly invite.',
  },
]

const FAQ_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ_EN.map(({ q, a }) => ({
    '@type': 'Question',
    name: q,
    acceptedAnswer: { '@type': 'Answer', text: a },
  })),
}

export default function HelpPage() {
  const { t, lang } = useTranslation()
  const [openFaq, setOpenFaq] = useState(null)

  useSeoMeta({
    title: t('help.meta_title'),
    description: t('help.meta_desc'),
    canonical: 'https://amendly.eu/help',
    lang: lang || 'en',
  })

  const faqs = [
    { q: t('help.q1'), a: t('help.a1') },
    { q: t('help.q2'), a: t('help.a2') },
    { q: t('help.q3'), a: t('help.a3') },
    { q: t('help.q4'), a: t('help.a4') },
    { q: t('help.q5'), a: t('help.a5') },
  ]

  const features = [
    {
      icon: <FileText className="w-4 h-4" />,
      title: t('help.feature_diff_title'),
      desc: t('help.feature_diff_desc'),
      illustration: <IllustrationDiff />,
    },
    {
      icon: <Users className="w-4 h-4" />,
      title: t('help.feature_roles_title'),
      desc: t('help.feature_roles_desc'),
      illustration: <IllustrationOrg />,
    },
    {
      icon: <Download className="w-4 h-4" />,
      title: t('help.feature_export_title'),
      desc: t('help.feature_export_desc'),
      illustration: <IllustrationExport />,
    },
    {
      icon: <Activity className="w-4 h-4" />,
      title: t('help.feature_activity_title'),
      desc: t('help.feature_activity_desc'),
      illustration: <IllustrationDocument />,
    },
  ]

  return (
    <div className="min-h-screen font-body text-slate-800 flex flex-col bg-slate-50">
      <JsonLd data={FAQ_JSON_LD} />
      <PublicHeader />

      <main className="flex-grow">

        {/* ---------------------------------------------------------------- */}
        {/* Hero                                                              */}
        {/* ---------------------------------------------------------------- */}
        <div className="bg-amendly-blue py-20 px-4 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            {t('help.hero_title')}
          </h1>
          <p className="text-blue-200 text-lg mb-8">
            {t('help.guide_subtitle')}
          </p>
          <div className="max-w-2xl mx-auto relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder={t('help.search_placeholder')}
              className="w-full pl-12 pr-6 py-4 rounded-xl shadow-lg border-none focus:ring-4 focus:ring-blue-300 outline-none text-lg text-slate-800"
            />
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Quick-action cards                                                */}
        {/* ---------------------------------------------------------------- */}
        <div className="max-w-4xl mx-auto px-4 -mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              to="/support"
              className="bg-white p-5 rounded-2xl shadow border border-gray-100 hover:shadow-md transition-shadow flex items-start gap-4"
            >
              <div className="w-11 h-11 bg-blue-50 text-amendly-blue rounded-xl flex items-center justify-center shrink-0">
                <MessageCircle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 mb-1">{t('help.contact_support')}</h3>
                <p className="text-gray-500 text-sm">{t('help.contact_support_desc')}</p>
              </div>
            </Link>
            <div className="bg-white p-5 rounded-2xl shadow border border-gray-100 flex items-start gap-4 opacity-60 cursor-not-allowed">
              <div className="w-11 h-11 bg-blue-50 text-amendly-blue rounded-xl flex items-center justify-center shrink-0">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 mb-1">{t('help.read_docs')}</h3>
                <p className="text-gray-500 text-sm">{t('help.docs_desc')}</p>
              </div>
            </div>
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Getting started guide                                             */}
        {/* ---------------------------------------------------------------- */}
        <section className="max-w-4xl mx-auto px-4 mt-20">
          <h2 className="text-3xl font-bold text-slate-900 mb-2">{t('help.guide_title')}</h2>
          <p className="text-gray-500 mb-10">{t('help.guide_subtitle')}</p>

          <div className="space-y-12">
            <GuideStep
              number={1}
              title={t('help.guide_step1_title')}
              desc={t('help.guide_step1_desc')}
              illustration={<IllustrationOrg />}
            />
            <div className="border-l-2 border-dashed border-blue-200 ml-5 pl-0 py-2" />
            <GuideStep
              number={2}
              title={t('help.guide_step2_title')}
              desc={t('help.guide_step2_desc')}
              illustration={<IllustrationDocument />}
            />
            <div className="border-l-2 border-dashed border-blue-200 ml-5 pl-0 py-2" />
            <GuideStep
              number={3}
              title={t('help.guide_step3_title')}
              desc={t('help.guide_step3_desc')}
              illustration={<IllustrationExport />}
            />
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Key features                                                      */}
        {/* ---------------------------------------------------------------- */}
        <section className="max-w-4xl mx-auto px-4 mt-24">
          <h2 className="text-3xl font-bold text-slate-900 mb-2">{t('help.feature_section_title')}</h2>
          <p className="text-gray-500 mb-10">{t('help.guide_subtitle')}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {features.map((f, i) => (
              <FeatureCard key={i} {...f} />
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* FAQ                                                               */}
        {/* ---------------------------------------------------------------- */}
        <section className="max-w-4xl mx-auto px-4 mt-24">
          <h2 className="text-3xl font-bold text-slate-900 mb-8">{t('help.faq_title')}</h2>
          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <div
                key={i}
                className="bg-white border border-gray-100 rounded-xl overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between gap-4 px-6 py-5 text-left"
                  aria-expanded={openFaq === i}
                >
                  <span className="text-base font-semibold text-slate-900">{faq.q}</span>
                  <ChevronDown
                    className={`w-5 h-5 text-gray-400 shrink-0 transition-transform duration-200 ${openFaq === i ? 'rotate-180' : ''}`}
                  />
                </button>
                {openFaq === i && (
                  <div className="px-6 pb-5 text-gray-600 leading-relaxed border-t border-gray-50 pt-4">
                    {faq.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Support CTA                                                       */}
        {/* ---------------------------------------------------------------- */}
        <section className="max-w-4xl mx-auto px-4 mt-20 mb-24">
          <div className="bg-amendly-blue rounded-2xl p-10 flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="text-center md:text-left">
              <h2 className="text-2xl font-bold text-white mb-2">{t('help.support_cta_title')}</h2>
              <p className="text-blue-200">{t('help.support_cta_desc')}</p>
            </div>
            <Link
              to="/support"
              className="shrink-0 px-8 py-3 bg-white text-amendly-blue font-bold rounded-xl hover:bg-blue-50 transition-colors"
            >
              {t('help.support_cta_btn')}
            </Link>
          </div>
        </section>

      </main>

      <PublicFooter />
    </div>
  )
}
