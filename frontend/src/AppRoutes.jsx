/**
 * AppRoutes — shared route tree used by both client and server entry points.
 *
 * This component is imported by:
 *   - src/App.jsx        (client: wrapped in <BrowserRouter>)
 *   - src/entry-server.jsx (server: wrapped in <StaticRouter> for prerendering)
 *
 * Routes:
 *   /                            → LandingPage (public marketing page)
 *   /pricing                     → Dedicated pricing page (public — prerendered)
 *   /legal/terms                 → Terms of Service (public static page)
 *   /legal/privacy               → Privacy Policy (public static page)
 *   /login                       → Login page (magic link + Google SSO)
 *   /auth/verify                 → Magic-link token exchange (reads ?token)
 *   /auth/callback               → OAuth token handler (reads URL fragment)
 *   /invitations/accept          → Accept an org invite by token
 *   /dashboard                   → Dashboard (protected)
 *   /account/settings            → Account settings (protected)
 *   /orgs/:slug                  → Organisation detail (protected)
 *   /orgs/:slug/settings         → Organisation settings (protected, owner only)
 *   /orgs/:slug/billing          → Billing (protected, owner only)
 *   /orgs/:slug/documents/:id    → Document view (protected)
 *   /admin/dashboard             → Admin overview dashboard (protected, superuser only)
 *   /admin/pricing               → Admin pricing interface (protected, superuser only)
 *   /admin/email-templates       → Admin email template editor (protected, superuser only)
 *   /admin/prospects             → Admin prospect CRM (protected, superuser only)
 *   /admin/users                 → Admin user management (protected, superuser only)
 *   /orgs/:slug/documents/:id/contribute → ContributorSubmission (protected, any member)
 *   /orgs/:slug/documents/:id/review    → ReviewView (protected, any member — export restricted to owner/admin)
 *   /contribute/:token                  → PublicContribution (public — no auth, unauthenticated amendment submission)
 *
 * CookieBanner is included so it appears on every client-side route.
 * During SSR it renders to nothing meaningful (no localStorage in Node.js),
 * which is acceptable — the banner is a client-only UX element.
 *
 * Props: none
 */

import { Suspense, lazy, useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import CookieBanner from './components/CookieBanner'
import ErrorBoundary from './components/ErrorBoundary'
import { useConsent } from './hooks/useConsent'
import AcceptInvite from './pages/AcceptInvite'
import AuthCallback from './pages/AuthCallback'
import MagicLinkVerify from './pages/MagicLinkVerify'
import LandingPage from './pages/LandingPage'
import Login from './pages/Login'
import ContactPage from './pages/ContactPage'
import AboutPage from './pages/AboutPage'
import PricingPage from './pages/PricingPage'
import PrivacyPage from './pages/PrivacyPage'
import TermsPage from './pages/TermsPage'
import DpaPage from './pages/DpaPage'
import PublicContribution from './pages/PublicContribution'
import FeaturesPage from './pages/FeaturesPage'
import HelpPage from './pages/HelpPage'
import BlogIndex from './pages/BlogIndex'
const BlogPost = lazy(() => import('./pages/BlogPost'))
const AccountSettings = lazy(() => import('./pages/AccountSettings'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const AdminEmailTemplates = lazy(() => import('./pages/AdminEmailTemplates'))
const AdminProspects = lazy(() => import('./pages/AdminProspects'))
const AdminPricing = lazy(() => import('./pages/AdminPricing'))
const AdminUsers = lazy(() => import('./pages/AdminUsers'))
const Billing = lazy(() => import('./pages/Billing'))
const ContributorSubmission = lazy(() => import('./pages/ContributorSubmission'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const DocumentView = lazy(() => import('./pages/DocumentView'))
const OrgDetail = lazy(() => import('./pages/OrgDetail'))
const OrgSettings = lazy(() => import('./pages/OrgSettings'))
const ReviewView = lazy(() => import('./pages/ReviewView'))
const SupportPage = lazy(() => import('./pages/SupportPage'))

/**
 * Inject the Plausible Analytics script into the document <head>.
 *
 * Uses the value of the VITE_PLAUSIBLE_DOMAIN environment variable to
 * configure the script's `data-domain` attribute. If the variable is not set
 * (e.g. in local development without a Plausible account), the function is a
 * no-op so the rest of the app is unaffected.
 *
 * This function must only be called after the user has accepted cookies.
 * It is idempotent — calling it twice does not inject a second script.
 *
 * @returns {void}
 */
function loadPlausible() {
  const domain = import.meta.env.VITE_PLAUSIBLE_DOMAIN
  if (!domain) return
  if (document.getElementById('plausible-script')) return

  const baseUrl = (import.meta.env.VITE_PLAUSIBLE_BASE_URL || 'https://plausible.io').replace(/\/$/, '')

  const script = document.createElement('script')
  script.id = 'plausible-script'
  script.defer = true
  script.setAttribute('data-domain', domain)
  script.setAttribute('data-api', `${baseUrl}/api/event`)
  script.src = `${baseUrl}/js/script.js`
  document.head.appendChild(script)
}

/**
 * The full route tree + analytics guard.
 * Must be rendered inside a Router (BrowserRouter on client, StaticRouter on server).
 *
 * @returns {React.ReactElement}
 */
export default function AppRoutes() {
  const { accepted } = useConsent()

  useEffect(() => {
    if (accepted) loadPlausible()
  }, [accepted])

  return (
    <>
      <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/features" element={<FeaturesPage />} />
            <Route path="/help" element={<HelpPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/legal/terms" element={<TermsPage />} />
            <Route path="/legal/privacy" element={<PrivacyPage />} />
            <Route path="/legal/dpa" element={<DpaPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/blog" element={<BlogIndex />} />
            <Route path="/blog/:slug" element={<BlogPost />} />
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/auth/verify" element={<MagicLinkVerify />} />
            <Route path="/invitations/accept" element={<AcceptInvite />} />
            <Route path="/contribute/:token" element={<PublicContribution />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/account/settings"
              element={
                <ProtectedRoute>
                  <AccountSettings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orgs/:slug"
              element={
                <ProtectedRoute>
                  <OrgDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orgs/:slug/settings"
              element={
                <ProtectedRoute>
                  <OrgSettings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orgs/:slug/billing"
              element={
                <ProtectedRoute>
                  <Billing />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orgs/:slug/documents/:id"
              element={
                <ProtectedRoute>
                  <DocumentView />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/dashboard"
              element={
                <ProtectedRoute>
                  <AdminDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/pricing"
              element={
                <ProtectedRoute>
                  <AdminPricing />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/email-templates"
              element={
                <ProtectedRoute>
                  <AdminEmailTemplates />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/prospects"
              element={
                <ProtectedRoute>
                  <AdminProspects />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/users"
              element={
                <ProtectedRoute>
                  <AdminUsers />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orgs/:slug/documents/:id/contribute"
              element={
                <ProtectedRoute>
                  <ContributorSubmission />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orgs/:slug/documents/:id/review"
              element={
                <ProtectedRoute>
                  <ReviewView />
                </ProtectedRoute>
              }
            />
            <Route
              path="/support"
              element={
                <ProtectedRoute>
                  <SupportPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </ErrorBoundary>

      {/* GDPR cookie consent banner — visible on every route until dismissed */}
      <CookieBanner />
    </>
  )
}

function RouteFallback() {
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <span className="font-body text-body-md text-outline">Loading…</span>
    </div>
  )
}
