import { useState } from 'react'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import JsonLd from '../components/JsonLd'
import { useTranslation } from '../hooks/useTranslation'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { Send } from 'lucide-react'
import { supportClient } from '../lib/support'

const JSON_LD_CONTACT = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'Amendly',
  url: 'https://amendly.eu',
  contactPoint: {
    '@type': 'ContactPoint',
    contactType: 'customer support',
    availableLanguage: ['English', 'French', 'German', 'Spanish'],
    url: 'https://amendly.eu/contact',
  },
}

export default function ContactPage() {
  const { t, lang } = useTranslation()
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)

  useSeoMeta({
    title: t('contact.meta_title'),
    description: t('contact.meta_desc'),
    canonical: 'https://amendly.eu/contact',
    lang: lang || 'en',
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setStatus('sending')

    // Honeypot validation
    const formData = new FormData(e.currentTarget)
    if (formData.get('website')) {
      // Bot detected - we silently pretend it worked to confuse the bot
      setStatus('sent')
      return
    }

    try {
      await supportClient.sendContactMessage({
        first_name: String(formData.get('firstName') ?? ''),
        last_name: String(formData.get('lastName') ?? ''),
        email: String(formData.get('email') ?? ''),
        message: String(formData.get('message') ?? ''),
        website: String(formData.get('website') ?? ''),
      })
      setStatus('sent')
    } catch (err) {
      setError(err?.message ?? t('contact.error'))
      setStatus('idle')
    }
  }

  return (
    <div className="min-h-screen font-body text-slate-800 flex flex-col relative overflow-hidden bg-amendly-light">
      <JsonLd data={JSON_LD_CONTACT} />
      <PublicHeader />

      <main className="flex-grow pt-24 pb-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          
          <div className="text-center max-w-3xl mx-auto mb-20 animate-fade-in-up">
            <h1 className="font-display font-black text-5xl md:text-6xl text-amendly-dark tracking-tight mb-8">
              {t('contact.hero_title_1')} <br />
              <span className="text-amendly-blue relative inline-block">
                {t('contact.hero_title_2')}
                <svg className="absolute w-full h-3 -bottom-1 left-0 text-blue-200" fill="currentColor" viewBox="0 0 100 20" preserveAspectRatio="none">
                  <path d="M0 10 Q 50 20 100 10 Q 50 0 0 10 Z"></path>
                </svg>
              </span>
            </h1>
            <p className="text-xl text-amendly-gray leading-relaxed font-medium">
              {t('contact.hero_subtitle')}
            </p>
          </div>

          <div className="max-w-3xl mx-auto">
            
            {/* Contact Form */}
            <div className="bg-white rounded-2xl p-10 border border-gray-100 shadow-xl shadow-slate-200/50">
              {status === 'sent' ? (
              <div className="text-center py-16">
                <div className="w-20 h-20 bg-green-100 text-green-500 rounded-full flex items-center justify-center mx-auto mb-6">
                  <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-slate-900 mb-4">{t('contact.success.title')}</h3>
                <p className="text-gray-600 text-lg mb-8 max-w-md mx-auto">
                  {t('contact.success.desc')}
                </p>
                <button 
                  onClick={() => { setStatus('idle'); setError(null) }}
                  className="px-8 py-4 bg-amendly-blue text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
                >
                  {t('contact.success.button')}
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Honeypot field for bot protection */}
                <div className="hidden" aria-hidden="true">
                  <label htmlFor="website">Website</label>
                  <input type="text" id="website" name="website" tabIndex="-1" autoComplete="off" />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div>
                      <label htmlFor="firstName" className="block text-sm font-semibold text-amendly-dark mb-2">{t('contact.first_name')}</label>
                      <input type="text" id="firstName" name="firstName" required autoComplete="given-name" className="w-full bg-slate-50 border border-gray-200 rounded-lg px-4 py-3 text-amendly-dark focus:ring-2 focus:ring-amendly-blue focus:border-amendly-blue outline-none transition-all" />
                    </div>
                    <div>
                      <label htmlFor="lastName" className="block text-sm font-semibold text-amendly-dark mb-2">{t('contact.last_name')}</label>
                      <input type="text" id="lastName" name="lastName" required autoComplete="family-name" className="w-full bg-slate-50 border border-gray-200 rounded-lg px-4 py-3 text-amendly-dark focus:ring-2 focus:ring-amendly-blue focus:border-amendly-blue outline-none transition-all" />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="email" className="block text-sm font-semibold text-amendly-dark mb-2">{t('contact.email')}</label>
                    <input type="email" id="email" name="email" required autoComplete="email" className="w-full bg-slate-50 border border-gray-200 rounded-lg px-4 py-3 text-amendly-dark focus:ring-2 focus:ring-amendly-blue focus:border-amendly-blue outline-none transition-all" placeholder="jane@example.com" />
                  </div>
                  <div>
                    <label htmlFor="message" className="block text-sm font-semibold text-amendly-dark mb-2">{t('contact.message')}</label>
                    <textarea id="message" name="message" rows="4" required className="w-full bg-slate-50 border border-gray-200 rounded-lg px-4 py-3 text-amendly-dark focus:ring-2 focus:ring-amendly-blue focus:border-amendly-blue outline-none transition-all resize-none" placeholder={t('contact.message_placeholder')}></textarea>
                  </div>
                  {error && (
                    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      {error}
                    </div>
                  )}
                  <button type="submit" disabled={status === 'sending'} className="w-full bg-amendly-blue hover:bg-blue-700 text-white font-bold text-lg rounded-xl px-8 py-4 transition-all shadow-lg shadow-blue-500/30 flex justify-center items-center gap-2 group disabled:opacity-60 disabled:cursor-not-allowed">
                    {status === 'sending' ? t('contact.sending') : t('contact.send_btn')}
                    {status !== 'sending' && <Send className="w-5 h-5 group-hover:translate-x-1 transition-transform" />}
                  </button>
                </form>
              )}
            </div>

          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  )
}
