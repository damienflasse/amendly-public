import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import PublicFooter from '../components/PublicFooter'
import { useSeoMeta } from '../hooks/useSeoMeta'
import { posts } from '../blog/posts'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export default function BlogIndex() {
  useSeoMeta({
    title: 'Blog — Amendly',
    description:
      'Insights on amendment management, governance, and collaborative decision-making for associations, federations, and NGOs.',
    canonical: 'https://amendly.eu/blog',
    lang: 'en',
  })

  return (
    <div className="min-h-screen font-body text-slate-800 flex flex-col bg-white">
      <PublicHeader />

      <main className="flex-grow">
        {/* Hero */}
        <section className="pt-32 pb-16 px-4 sm:px-6 lg:px-8 bg-amendly-light">
          <div className="max-w-3xl mx-auto">
            <p className="text-sm font-semibold uppercase tracking-widest text-amendly-blue mb-4">
              Blog
            </p>
            <h1 className="font-display font-black text-4xl md:text-5xl text-amendly-dark tracking-tight mb-6">
              Amendment management,<br />in practice.
            </h1>
            <p className="text-lg text-amendly-gray leading-relaxed">
              Field notes from building Amendly — for the people who run congresses, general
              assemblies, and working groups.
            </p>
          </div>
        </section>

        {/* Article list */}
        <section className="py-16 px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto space-y-12">
            {posts.map((post) => (
              <article key={post.slug}>
                <Link to={`/blog/${post.slug}`} className="group block">
                  <p className="text-sm text-amendly-gray mb-2">
                    {formatDate(post.date)} · {post.readingTime} read
                  </p>
                  <h2 className="font-display font-black text-2xl text-amendly-dark tracking-tight mb-3 group-hover:text-amendly-blue transition-colors">
                    {post.title}
                  </h2>
                  <p className="text-base text-amendly-gray leading-relaxed mb-4">
                    {post.description}
                  </p>
                  <span className="text-sm font-semibold text-amendly-blue group-hover:underline">
                    Read article →
                  </span>
                </Link>
              </article>
            ))}
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  )
}
