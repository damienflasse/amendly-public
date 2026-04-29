import { Link } from 'react-router-dom'
import { useTranslation } from '../hooks/useTranslation'
import Logo from './Logo'

export default function PublicFooter() {
  const { t } = useTranslation()
  const year = new Date().getFullYear();

  return (
    <footer className="bg-white border-t border-gray-100 pt-16 pb-8" data-purpose="global-footer">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-12 mb-16">
          <div className="col-span-2">
            <Link to="/" onClick={() => window.scrollTo(0, 0)} className="block mb-6 hover:opacity-80 transition-opacity">
              <Logo />
            </Link>
            <div className="flex gap-5 mt-6">
              <a className="text-gray-400 hover:text-amendly-blue transition" href="/">
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"></path></svg>
              </a>
              <a className="text-gray-400 hover:text-amendly-blue transition" href="/">
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"></path></svg>
              </a>
              <a className="text-gray-400 hover:text-amendly-blue transition" href="/">
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M22.675 0h-21.35c-.732 0-1.325.593-1.325 1.325v21.351c0 .731.593 1.324 1.325 1.324h11.495v-9.294h-3.128v-3.622h3.128v-2.671c0-3.1 1.893-4.788 4.659-4.788 1.325 0 2.463.099 2.795.143v3.24l-1.918.001c-1.504 0-1.795.715-1.795 1.763v2.312h3.587l-.467 3.622h-3.12v9.293h6.116c.73 0 1.323-.593 1.323-1.325v-21.35c0-.732-.593-1.325-1.325-1.325z"></path></svg>
              </a>
            </div>
          </div>
          <div data-purpose="footer-column">
            <h5 className="font-bold text-slate-900 mb-6 flex items-center gap-1 cursor-pointer hover:text-amendly-blue">
              {t('nav_public.product')}
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
            </h5>
            <ul className="space-y-4 text-sm text-gray-500">
              <li><a className="hover:text-amendly-blue transition" href="/#features">{t('nav_public.features')}</a></li>
              <li><Link className="hover:text-amendly-blue transition" to="/pricing">Pricing</Link></li>
              <li><a className="hover:text-amendly-blue transition" href="/pricing#faq">{t('nav_public.faq')}</a></li>
              <li><Link className="hover:text-amendly-blue transition" to="/help">{t('nav_public.help_center')}</Link></li>
            </ul>
          </div>
          <div data-purpose="footer-column">
            <h5 className="font-bold text-slate-900 mb-6 flex items-center gap-1 cursor-pointer hover:text-amendly-blue">
              {t('nav_public.company')}
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
            </h5>
            <ul className="space-y-4 text-sm text-gray-500">
              <li><Link className="hover:text-amendly-blue transition" to="/about">{t('nav_public.about_us')}</Link></li>
              <li><Link className="hover:text-amendly-blue transition" to="/blog">Blog</Link></li>
              <li><Link className="hover:text-amendly-blue transition" to="/contact">{t('nav_public.contact_us')}</Link></li>
            </ul>
          </div>
          <div data-purpose="footer-column">
            <h5 className="font-bold text-slate-900 mb-6 flex items-center gap-1 cursor-pointer hover:text-amendly-blue">
              {t('nav_public.legal')}
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
            </h5>
            <ul className="space-y-4 text-sm text-gray-500">
              <li><Link className="hover:text-amendly-blue transition" to="/legal/terms">Terms of Service</Link></li>
              <li><Link className="hover:text-amendly-blue transition" to="/legal/privacy">Privacy Policy</Link></li>
              <li><Link className="hover:text-amendly-blue transition" to="/legal/dpa">DPA</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-gray-100 pt-8 flex flex-col md:flex-row justify-between items-center text-sm text-gray-400">
          <p>© {year} Amendly — a product by <a href="https://www.athcode.com" target="_blank" rel="noopener noreferrer" className="hover:text-amendly-blue transition">athcode.com</a>. All rights reserved.</p>
          <Link className="hover:text-amendly-blue transition" to="/contact">{t('nav_public.contact_us')}</Link>
        </div>
      </div>
    </footer>
  )
}
