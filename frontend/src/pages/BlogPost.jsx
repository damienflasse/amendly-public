import { lazy, Suspense } from 'react'
import { useParams, Link, Navigate } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import JsonLd from '../components/JsonLd'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { posts } from '../blog/posts'

/**
 * Map of slug → lazy-loaded post content component.
 *
 * To add a new post:
 *   1. Create the JSX file in src/blog/posts/{slug}.jsx
 *   2. Add the slug to posts.js
 *   3. Add one line here:
 *        'your-slug': lazy(() => import('../blog/posts/your-slug.jsx')),
 */
const postComponents = {
  'how-to-prepare-a-general-assembly-with-amendments': lazy(() =>
    import('../blog/posts/how-to-prepare-a-general-assembly-with-amendments.jsx')
  ),
  'preparer-ag-avec-amendements': lazy(() =>
    import('../blog/posts/preparer-ag-avec-amendements.jsx')
  ),
  'broken-amendment-process': lazy(() =>
    import('../blog/posts/broken-amendment-process.jsx')
  ),
  'gestion-des-amendements-dans-les-ong-pourquoi-les-outils-manuels-atteignent-leurs-limites': lazy(() =>
    import('../blog/posts/gestion-des-amendements-dans-les-ong-pourquoi-les-outils-manuels-atteignent-leurs-limites.jsx')
  ),
  'managing-amendments-in-ngos-why-manual-tools-are-reaching-their-limits': lazy(() =>
    import('../blog/posts/managing-amendments-in-ngos-why-manual-tools-are-reaching-their-limits.jsx')
  ),
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export default function BlogPost() {
  const { slug } = useParams()

  const post = posts.find((p) => p.slug === slug)
  const PostContent = postComponents[slug]

  // Call hook unconditionally, use optional chaining and fallbacks for undefined state
  useSeoMeta({
    title: post ? `${post.title} — Amendly Blog` : 'Blog Not Found — Amendly',
    description: post?.description || '',
    canonical: `https://amendly.eu/blog/${slug}`,
    ogType: 'article',
    lang: 'en',
  })

  // Unknown slug → 404 redirect
  if (!post || !PostContent) {
    return <Navigate to="/blog" replace />
  }

  const canonicalUrl = `https://amendly.eu/blog/${slug}`

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: post.title,
    description: post.description,
    datePublished: post.date,
    author: {
      '@type': 'Person',
      name: post.author,
    },
    publisher: {
      '@type': 'Organization',
      name: 'Amendly',
      url: 'https://amendly.eu',
    },
    url: canonicalUrl,
    mainEntityOfPage: canonicalUrl,
  }

  return (
    <div className="min-h-screen font-body text-slate-800 flex flex-col bg-white">
      <JsonLd data={jsonLd} />
      <PublicHeader />

      <main className="flex-grow">
        {/* Article header */}
        <header className="pt-32 pb-12 px-4 sm:px-6 lg:px-8 bg-amendly-light">
          <div className="max-w-3xl mx-auto">
            <Link
              to="/blog"
              className="text-sm font-semibold text-amendly-blue hover:underline mb-8 inline-block"
            >
              ← Blog
            </Link>
            <p className="text-sm text-amendly-gray mb-4">
              {formatDate(post.date)} · {post.readingTime} read · By {post.author}
            </p>
            <h1 className="font-display font-black text-3xl md:text-4xl text-amendly-dark tracking-tight leading-tight">
              {post.title}
            </h1>
          </div>
        </header>

        {/* Article body */}
        <div className="px-4 sm:px-6 lg:px-8 py-16">
          <div
            className="
              max-w-3xl mx-auto
              [&_p]:text-on-surface [&_p]:leading-[1.8] [&_p]:mb-6 [&_p]:text-[1.0625rem]
              [&_h2]:font-display [&_h2]:font-black [&_h2]:text-2xl [&_h2]:text-amendly-dark
              [&_h2]:tracking-tight [&_h2]:mt-12 [&_h2]:mb-4
              [&_hr]:border-0 [&_hr]:border-t [&_hr]:border-surface-container-highest [&_hr]:my-10
              [&_em]:text-amendly-gray
              [&_strong]:font-semibold [&_strong]:text-amendly-dark
            "
          >
            <Suspense fallback={<PostFallback />}>
              <PostContent />
            </Suspense>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  )
}

function PostFallback() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-4 bg-surface-container-low rounded w-3/4" />
      <div className="h-4 bg-surface-container-low rounded w-full" />
      <div className="h-4 bg-surface-container-low rounded w-5/6" />
    </div>
  )
}
