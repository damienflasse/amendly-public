import React from 'react'
import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { CheckCircle2, Shield, Users, Zap } from 'lucide-react'

export default function AboutPage() {
  const { t, lang } = useTranslation()

  useSeoMeta({
    title: t('about.meta_title'),
    description: t('about.meta_desc'),
    canonical: 'https://amendly.eu/about',
    lang: lang || 'en',
  })

  return (
    <div className="min-h-screen font-body text-slate-800 flex flex-col relative overflow-hidden bg-white">
      <PublicHeader />

      <main className="flex-grow">
        {/* Hero Section */}
        <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8 bg-amendly-light relative overflow-hidden">
          <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/3 w-[800px] h-[800px] bg-blue-100 rounded-full blur-[120px] opacity-60"></div>
          
          <div className="max-w-4xl mx-auto text-center relative z-10">
            <h1 className="font-display font-black text-5xl md:text-7xl text-amendly-dark tracking-tight mb-8">
              {t('about.hero_title_1')} <br />
              <span className="relative inline-block">
                {t('about.hero_title_2')}
                <svg className="absolute w-full h-3 -bottom-1 left-0 text-amber-300" fill="currentColor" viewBox="0 0 100 20" preserveAspectRatio="none">
                  <path d="M0 10 Q 50 20 100 10 Q 50 0 0 10 Z"></path>
                </svg>
              </span>
            </h1>
            <p className="text-xl md:text-2xl text-amendly-gray leading-relaxed font-medium mb-12">
              {t('about.hero_subtitle')}
            </p>
          </div>
        </section>

        {/* Content Section */}
        <section className="py-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-20 items-center">
            
            <div className="space-y-8">
              <h2 className="font-display font-black text-4xl text-amendly-dark tracking-tight">
                {t('about.section_title')}
              </h2>
              <div className="space-y-6 text-lg text-amendly-gray leading-relaxed">
                <p>{t('about.p1')}</p>
                <p>{t('about.p2')}</p>
                <p>{t('about.p3')}</p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-6">
              {[
                { icon: Shield, title: t('about.feature_1_title'), desc: t('about.feature_1_desc') },
                { icon: Users, title: t('about.feature_2_title'), desc: t('about.feature_2_desc') },
                { icon: Zap, title: t('about.feature_3_title'), desc: t('about.feature_3_desc') },
                { icon: CheckCircle2, title: t('about.feature_4_title'), desc: t('about.feature_4_desc') }
              ].map((val, idx) => (
                <div key={idx} className="bg-amendly-light rounded-2xl p-8 border border-gray-100 hover:shadow-lg transition-shadow">
                  <div className="w-12 h-12 bg-white text-amendly-blue rounded-xl flex items-center justify-center mb-6 shadow-sm">
                    <val.icon className="w-6 h-6" />
                  </div>
                  <h3 className="font-display font-bold text-xl text-amendly-dark mb-3">{val.title}</h3>
                  <p className="text-amendly-gray text-sm">{val.desc}</p>
                </div>
              ))}
            </div>

          </div>
        </section>

        {/* Call to Action */}
        <section className="py-24 bg-amendly-dark text-center px-4">
          <h2 className="font-display font-black text-4xl md:text-5xl text-white mb-6">
            {t('about.cta_title')}
          </h2>
          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto">
            {t('about.cta_subtitle')}
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Link to="/pricing" className="bg-amendly-blue hover:bg-blue-600 text-white font-bold text-lg rounded-xl px-10 py-5 transition-all shadow-lg flex items-center justify-center">
              {t('about.cta_pricing')}
            </Link>
            <Link to="/contact" className="bg-white/10 hover:bg-white/20 text-white font-bold text-lg rounded-xl px-10 py-5 transition-all flex items-center justify-center">
              {t('about.cta_contact')}
            </Link>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  )
}
