/**
 * Blog post manifest.
 *
 * Each entry describes one article. The slug must match:
 *   1. The filename in frontend/src/blog/posts/{slug}.jsx
 *   2. The route  /blog/{slug}
 *
 * To publish a new article:
 *   1. Create frontend/src/blog/posts/{slug}.jsx  (the JSX content)
 *   2. Add an entry here
 *   3. Add the slug to the postComponents map in BlogPost.jsx
 *   That's it — prerendering picks it up automatically.
 *
 * Fields:
 *   slug        — URL-safe identifier, kebab-case
 *   title       — Full article title (used in <h1>, OG, JSON-LD)
 *   description — ≤160 chars — meta description + OG description
 *   date        — ISO 8601 publication date (YYYY-MM-DD)
 *   author      — Displayed byline
 *   readingTime — Estimated read time, displayed to users
 */
export const posts = [
  {
    slug: 'how-to-prepare-a-general-assembly-with-amendments',
    title: "How to prepare a general assembly with amendments: a step-by-step guide",
    description: "A general assembly with amendments doesn't run itself. Here is a structured four-step method to collect, review, and consolidate amendments — from setting rules to the final export.",
    date: '2026-04-26',
    author: 'Damien Flasse',
    readingTime: '5 min',
  },
  {
    slug: 'preparer-ag-avec-amendements',
    title: "Comment préparer une assemblée générale avec des amendements : guide pas à pas",
    description: "Une AG avec des amendements, ça se prépare bien en amont. Voici une méthode en quatre étapes pour collecter, réviser et consolider les amendements — du cadrage à l'export final.",
    date: '2026-04-26',
    author: 'Damien Flasse',
    readingTime: '5 min',
  },
  {
    slug: 'managing-amendments-in-ngos-why-manual-tools-are-reaching-their-limits',
    title: "Managing amendments in NGOs: why manual tools are reaching their limits",
    description: "In the vast majority of associations, trade unions, and NGOs across Europe, amendment management still relies on two tools: a Word table and an email inbox. …",
    date: '2026-05-05',
    author: 'Damien Flasse',
    readingTime: '4 min',
  },
  {
    slug: 'gestion-des-amendements-dans-les-ong-pourquoi-les-outils-manuels-atteignent-leurs-limites',
    title: "Gestion des amendements dans les ONG : pourquoi les outils manuels atteignent leurs limites",
    description: "Dans la quasi-totalité des associations, syndicats et ONG européennes, la gestion des amendements repose encore sur deux outils : un tableau Word et une boît…",
    date: '2026-05-05',
    author: 'Damien Flasse',
    readingTime: '5 min',
  },
  {
    slug: 'broken-amendment-process',
    title: "Why your General Assembly's amendment process is broken (and it's not your fault)",
    description:
      "Most organisations manage amendments with Word tables and email threads. Here is why that happens, and what it points to.",
    date: '2026-04-10',
    author: 'Damien Flasse',
    readingTime: '4 min',
  },
]
