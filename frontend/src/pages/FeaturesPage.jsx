import React from 'react'
import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { Layers, ShieldCheck, Zap, Users, Search, FileText } from 'lucide-react'

/**
 * Inline SVG illustration simulating the Amendly dashboard.
 * Replaces a missing hero_dashboard_preview.png with a no-dependency,
 * always-fresh visual that matches the "Editorial Ledger" design system.
 *
 * Props: none
 */
function DashboardIllustration({ t }) {
  return (
    <svg
      viewBox="0 0 640 400"
      xmlns="http://www.w3.org/2000/svg"
      className="w-full h-auto rounded-xl"
      role="img"
      aria-label="Amendly dashboard preview"
    >
      {/* App chrome */}
      <rect width="640" height="400" rx="10" fill="#1e293b" />

      {/* Top bar */}
      <rect width="640" height="40" rx="0" fill="#0f172a" />
      <rect x="0" y="0" width="640" height="40" rx="10" fill="#0f172a" />
      <rect x="0" y="20" width="640" height="20" fill="#0f172a" />
      {/* Window dots */}
      <circle cx="20" cy="20" r="5" fill="#ef4444" opacity="0.7" />
      <circle cx="36" cy="20" r="5" fill="#f59e0b" opacity="0.7" />
      <circle cx="52" cy="20" r="5" fill="#22c55e" opacity="0.7" />
      {/* URL bar */}
      <rect x="180" y="11" width="280" height="18" rx="4" fill="#1e293b" />
      <text x="320" y="23" textAnchor="middle" fill="#64748b" fontSize="8" fontFamily="Inter, sans-serif">amendly.eu/orgs/my-org/documents/42</text>

      {/* Left sidebar */}
      <rect x="0" y="40" width="150" height="360" fill="#0f172a" />
      {/* Logo area */}
      <text x="16" y="65" fill="#2563EB" fontSize="13" fontWeight="800" fontFamily="Inter, sans-serif">Amendly</text>
      {/* Nav items */}
      {[
        { y: 90,  label: t('features.ill_nav_dashboard', 'Dashboard'),   active: false },
        { y: 112, label: t('features.ill_nav_documents', 'Documents'),   active: true  },
        { y: 134, label: t('features.ill_nav_members', 'Members'),     active: false },
        { y: 156, label: t('features.ill_nav_activity', 'Activity'),    active: false },
        { y: 178, label: t('features.ill_nav_settings', 'Settings'),    active: false },
      ].map(({ y, label, active }) => (
        <g key={label}>
          {active && <rect x="8" y={y - 10} width="134" height="20" rx="5" fill="#1e3a8a" opacity="0.6" />}
          <text x="20" y={y + 4} fill={active ? '#93c5fd' : '#475569'} fontSize="9" fontFamily="Inter, sans-serif">{label}</text>
        </g>
      ))}
      {/* Sidebar separator */}
      <line x1="150" y1="40" x2="150" y2="400" stroke="#1e293b" strokeWidth="1" />

      {/* Main content area */}
      {/* Document header */}
      <rect x="158" y="50" width="474" height="50" fill="#1e293b" />
      <text x="170" y="68" fill="#f1f5f9" fontSize="12" fontWeight="700" fontFamily="Inter, sans-serif">{t('features.ill_doc_title', "Statuts de l'association — Réforme 2024")}</text>
      <text x="170" y="84" fill="#64748b" fontSize="8" fontFamily="Inter, sans-serif">{t('features.ill_doc_meta', 'Dernière modification il y a 2 heures · 8 amendements en attente')}</text>
      {/* Status badge */}
      <rect x="530" y="56" width="48" height="16" rx="4" fill="#166534" opacity="0.5" />
      <text x="554" y="67" textAnchor="middle" fill="#86efac" fontSize="7" fontWeight="600" fontFamily="Inter, sans-serif">{t('features.ill_status_open', 'OUVERT')}</text>
      {/* Export button */}
      <rect x="582" y="55" width="42" height="18" rx="4" fill="#2563EB" />
      <text x="603" y="67" textAnchor="middle" fill="white" fontSize="7" fontWeight="600" fontFamily="Inter, sans-serif">{t('features.ill_export', 'Export')}</text>

      {/* Divider */}
      <line x1="158" y1="100" x2="632" y2="100" stroke="#334155" strokeWidth="1" />

      {/* Amendment list — left column */}
      <text x="170" y="120" fill="#94a3b8" fontSize="8" fontWeight="600" fontFamily="Inter, sans-serif" letterSpacing="0.05em">{t('features.ill_amendments', 'AMENDEMENTS (8)')}</text>

      {/* Amendment cards */}
      {[
        { y: 130, status: t('features.ill_status_accepted', 'ACCEPTÉ'),  statusColor: '#86efac', statusBg: '#14532d', section: 'Article 3', author: 'M. Dupont', snippet: t('features.ill_snippet_1', 'Modifier la durée du mandat de 2 à 3 ans') },
        { y: 178, status: t('features.ill_status_pending', 'EN ATTENTE'), statusColor: '#fde68a', statusBg: '#713f12', section: 'Article 7', author: 'Mme. Martin', snippet: t('features.ill_snippet_2', 'Supprimer la clause relative aux cotisations') },
        { y: 226, status: t('features.ill_status_rejected', 'REFUSÉ'),   statusColor: '#fca5a5', statusBg: '#7f1d1d', section: 'Préambule', author: 'M. Bernard', snippet: t('features.ill_snippet_3', 'Ajouter un paragraphe sur la gouvernance') },
        { y: 274, status: t('features.ill_status_pending', 'EN ATTENTE'), statusColor: '#fde68a', statusBg: '#713f12', section: 'Article 12', author: 'Mme. Leblanc', snippet: t('features.ill_snippet_4', 'Réviser les modalités de vote électronique') },
      ].map(({ y, status, statusColor, statusBg, section, author, snippet }) => (
        <g key={y}>
          <rect x="160" y={y} width="220" height="42" rx="6" fill="#1e293b" />
          <rect x="160" y={y} width="4" height="42" rx="2" fill={statusColor} opacity="0.6" />
          <rect x="320" y={y + 6} width="52" height="13" rx="3" fill={statusBg} opacity="0.5" />
          <text x="346" y={y + 15} textAnchor="middle" fill={statusColor} fontSize="6" fontWeight="700" fontFamily="Inter, sans-serif">{status}</text>
          <text x="172" y={y + 14} fill="#94a3b8" fontSize="7" fontWeight="600" fontFamily="Inter, sans-serif">{section}</text>
          <text x="172" y={y + 26} fill="#cbd5e1" fontSize="8" fontFamily="Inter, sans-serif">{snippet.substring(0, 32)}…</text>
          <text x="172" y={y + 37} fill="#475569" fontSize="7" fontFamily="Inter, sans-serif">{author}</text>
        </g>
      ))}

      {/* Diff viewer — right panel */}
      <rect x="392" y="108" width="240" height="280" rx="8" fill="#0f172a" />
      <text x="404" y="126" fill="#94a3b8" fontSize="8" fontWeight="600" fontFamily="Inter, sans-serif" letterSpacing="0.05em">{t('features.ill_diff_title', 'APERÇU DU DIFF — Article 3')}</text>
      <line x1="392" y1="132" x2="632" y2="132" stroke="#1e293b" strokeWidth="1" />

      {/* Diff content */}
      <text x="404" y="150" fill="#94a3b8" fontSize="8" fontFamily="Inter, sans-serif">{t('features.ill_original', 'Texte original :')}</text>
      <rect x="404" y="156" width="212" height="44" rx="4" fill="#1e293b" />
      <text x="412" y="170" fill="#cbd5e1" fontSize="7.5" fontFamily="Inter, sans-serif">{t('features.ill_txt_1', 'Le mandat des membres du bureau')}</text>
      {/* Deletion */}
      <rect x="412" y="174" width="30" height="12" rx="2" fill="#7f1d1d" opacity="0.4" />
      <text x="412" y="183" fill="#fca5a5" fontSize="7.5" fontFamily="Inter, sans-serif" textDecoration="line-through">{t('features.ill_txt_2', '2 ans')}</text>
      <text x="444" y="183" fill="#cbd5e1" fontSize="7.5" fontFamily="Inter, sans-serif">{t('features.ill_txt_3', ' est renouvelable une fois.')}</text>

      <text x="404" y="218" fill="#94a3b8" fontSize="8" fontFamily="Inter, sans-serif">{t('features.ill_proposed', 'Texte proposé :')}</text>
      <rect x="404" y="224" width="212" height="44" rx="4" fill="#1e293b" />
      <text x="412" y="238" fill="#cbd5e1" fontSize="7.5" fontFamily="Inter, sans-serif">{t('features.ill_txt_1', 'Le mandat des membres du bureau')}</text>
      {/* Addition */}
      <rect x="412" y="242" width="30" height="12" rx="2" fill="#1e3a8a" opacity="0.5" />
      <text x="412" y="251" fill="#93c5fd" fontSize="7.5" fontWeight="700" fontFamily="Inter, sans-serif">{t('features.ill_txt_4', '3 ans')}</text>
      <text x="444" y="251" fill="#cbd5e1" fontSize="7.5" fontFamily="Inter, sans-serif">{t('features.ill_txt_3', ' est renouvelable une fois.')}</text>

      {/* Reactions */}
      <text x="404" y="286" fill="#94a3b8" fontSize="8" fontWeight="600" fontFamily="Inter, sans-serif">{t('features.ill_reactions', 'Réactions :')}</text>
      <rect x="404" y="292" width="46" height="16" rx="4" fill="#14532d" opacity="0.5" />
      <text x="427" y="302" textAnchor="middle" fill="#86efac" fontSize="7" fontFamily="Inter, sans-serif">👍 12</text>
      <rect x="456" y="292" width="46" height="16" rx="4" fill="#7f1d1d" opacity="0.4" />
      <text x="479" y="302" textAnchor="middle" fill="#fca5a5" fontSize="7" fontFamily="Inter, sans-serif">👎 3</text>

      {/* Action buttons */}
      <rect x="404" y="320" width="86" height="20" rx="4" fill="#15803d" />
      <text x="447" y="332" textAnchor="middle" fill="white" fontSize="7.5" fontWeight="600" fontFamily="Inter, sans-serif">{t('features.ill_accept', '✓ Accepter')}</text>
      <rect x="496" y="320" width="78" height="20" rx="4" fill="#991b1b" opacity="0.8" />
      <text x="535" y="332" textAnchor="middle" fill="#fca5a5" fontSize="7.5" fontWeight="600" fontFamily="Inter, sans-serif">{t('features.ill_reject', '✕ Refuser')}</text>

      {/* Bottom status bar */}
      <rect x="0" y="380" width="640" height="20" fill="#0f172a" />
      <text x="170" y="393" fill="#475569" fontSize="7" fontFamily="Inter, sans-serif">{t('features.ill_footer_stats', '4 acceptés · 8 en attente · 1 refusé')}</text>
      <text x="520" y="393" fill="#2563EB" fontSize="7" fontFamily="Inter, sans-serif">{t('features.ill_footer_status', 'Consolidation disponible')}</text>
    </svg>
  )
}

export default function FeaturesPage() {
  const { t, lang } = useTranslation()

  useSeoMeta({
    title: t('features.meta_title'),
    description: t('features.meta_desc'),
    canonical: 'https://amendly.eu/features',
    lang: lang || 'en',
  })

  const featuresList = [
    {
      icon: <Layers className="w-6 h-6" />,
      title: t('features.f1_title'),
      desc: t('features.f1_desc')
    },
    {
      icon: <Search className="w-6 h-6" />,
      title: t('features.f2_title'),
      desc: t('features.f2_desc')
    },
    {
      icon: <Users className="w-6 h-6" />,
      title: t('features.f3_title'),
      desc: t('features.f3_desc')
    },
    {
      icon: <Zap className="w-6 h-6" />,
      title: t('features.f4_title'),
      desc: t('features.f4_desc')
    },
    {
      icon: <ShieldCheck className="w-6 h-6" />,
      title: t('features.f5_title'),
      desc: t('features.f5_desc')
    },
    {
      icon: <FileText className="w-6 h-6" />,
      title: t('features.f6_title'),
      desc: t('features.f6_desc')
    }
  ]

  return (
    <div className="min-h-screen font-body text-slate-800 flex flex-col relative overflow-hidden bg-amendly-light">
      <PublicHeader />

      <main className="flex-grow pt-32 pb-24">
        {/* Hero Section */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center mb-24 animate-fade-in-up">
          <span className="inline-block px-3 py-1 mb-6 text-xs font-bold tracking-wider text-amendly-blue uppercase bg-blue-50 border border-blue-100 rounded-md">
            {t('features.badge')}
          </span>
          <h1 className="font-display font-black text-5xl md:text-6xl text-amendly-dark tracking-tight mb-8">
            {t('features.hero_title')}<br/>
            <span className="text-amendly-blue relative inline-block">
              {t('features.hero_title_highlight')}
              <svg className="absolute w-full h-3 -bottom-1 left-0 text-blue-200" fill="currentColor" viewBox="0 0 100 20" preserveAspectRatio="none">
                <path d="M0 10 Q 50 20 100 10 Q 50 0 0 10 Z"></path>
              </svg>
            </span>
          </h1>
          <p className="text-xl text-amendly-gray leading-relaxed font-medium max-w-3xl mx-auto mb-10">
            {t('features.hero_subtitle')}
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link to="/pricing" className="px-8 py-4 bg-amendly-blue text-white rounded-lg font-bold shadow-lg shadow-blue-500/30 hover:-translate-y-0.5 transition-all">
              {t('features.cta_primary')}
            </Link>
            <Link to="/contact" className="px-8 py-4 bg-white text-amendly-dark border border-gray-200 rounded-lg font-bold shadow-sm hover:border-gray-300 transition-all">
              {t('features.cta_secondary')}
            </Link>
          </div>
        </section>

        {/* Feature Grid */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 mb-32">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {featuresList.map((feature, idx) => (
              <div key={idx} className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all group">
                <div className="w-14 h-14 bg-blue-50 text-amendly-blue rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Deep Dive Section */}
        <section className="bg-slate-900 text-white py-24 my-24 relative overflow-hidden">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col lg:flex-row items-center gap-16 relative z-10">
            <div className="flex-1">
              <h2 className="text-3xl lg:text-5xl font-bold mb-6">{t('features.deep_title')}</h2>
              <p className="text-lg text-slate-400 mb-8 leading-relaxed">
                {t('features.deep_desc')}
              </p>
              <ul className="space-y-4">
                {[
                  t('features.benefit_1'),
                  t('features.benefit_2'),
                  t('features.benefit_3')
                ].map((text, idx) => (
                  <li key={idx} className="flex items-center gap-3">
                    <div className="w-6 h-6 bg-blue-500/20 text-blue-400 rounded-full flex items-center justify-center shrink-0">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                    </div>
                    <span className="text-slate-200">{text}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex-1 w-full bg-slate-800 rounded-2xl p-4 border border-slate-700 shadow-2xl">
              <DashboardIllustration t={t} />
            </div>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  )
}
