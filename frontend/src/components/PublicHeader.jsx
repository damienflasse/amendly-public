import { Link } from 'react-router-dom'
import { useTranslation } from '../hooks/useTranslation'
import LanguageSwitcher from './LanguageSwitcher'
import Logo from './Logo'

export default function PublicHeader() {
  const { t, lang, setLang } = useTranslation()

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100" data-purpose="sticky-navigation">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
        <div className="flex items-center gap-2" data-purpose="brand-logo">
          <Link to="/" onClick={() => window.scrollTo(0, 0)} className="hover:opacity-80 transition-opacity">
            <Logo />
          </Link>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
          <a className="hover:text-amendly-blue transition" href="/#features">{t('nav_public.features')}</a>
          <a className="hover:text-amendly-blue transition" href="/#how-it-works">{t('nav_public.how_it_works')}</a>
          <Link className="hover:text-amendly-blue transition" to="/pricing">{t('nav_public.pricing')}</Link>
          <Link className="hover:text-amendly-blue transition" to="/blog">Blog</Link>
          <Link className="hover:text-amendly-blue transition" to="/contact">{t('nav_public.contact')}</Link>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative group">
            <LanguageSwitcher lang={lang} setLang={setLang} />
          </div>
          <Link className="px-5 py-2.5 text-sm font-semibold text-white bg-amendly-blue rounded-lg shadow-sm hover:bg-blue-700 transition" to="/login">{t('nav_public.sign_in')}</Link>
          <Link className="px-5 py-2.5 text-sm font-semibold text-white bg-amendly-blue rounded-lg shadow-sm hover:bg-blue-700 transition" to="/">{t('nav_public.get_started')}</Link>
        </div>
      </nav>
    </header>
  )
}
