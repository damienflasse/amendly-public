/**
 * Blog post: "Why your General Assembly's amendment process is broken"
 *
 * This component returns the article body only — no layout, no header.
 * BlogPost.jsx wraps it with PublicHeader, PublicFooter, and prose styles.
 *
 * Authoring guide:
 *   - Use <h2> for section headings
 *   - Use <p> for paragraphs
 *   - Use <em> for italic emphasis
 *   - Use <strong> for bold
 *   - Use <hr /> for section breaks
 *   - Use <a href="..."> for links
 */
export default function BrokenAmendmentProcess() {
  return (
    <>
      <p>
        A colleague walked into my office one afternoon with a very specific request. He was managing
        amendments for a Congress Preparatory Committee — a serious responsibility, weeks of work
        ahead — and he'd heard there was software for this. The European Commission used something.
        Could I install it?
      </p>

      <p>I went to look.</p>

      <p>
        What I found was a monumental piece of enterprise software. Complex installation
        requirements, heavy infrastructure, designed for institutions with dedicated IT departments
        and procurement cycles measured in months. For a lean team preparing a congress, it was
        completely unusable. A sledgehammer for a task that needed a scalpel.
      </p>

      <p>So I asked him to show me exactly what he was doing.</p>

      <hr />

      <h2>The Word table that ate his evenings</h2>

      <p>His workflow went like this.</p>

      <p>
        He had a base text — the kind of foundational document that gets debated at every serious
        congress. He'd split it into sections and built a Word table to track everything. When
        amendments arrived by email — and they arrived constantly, from delegates across multiple
        countries — he copied each one manually into the table. He placed it in the right section.
        He italicised the proposed new text. He bolded whatever was being replaced. He tracked who
        submitted it, when, and what the current status was.
      </p>

      <p>Every. Single. One. By hand.</p>

      <p>
        When an amendment was updated or withdrawn, he updated the table. When two amendments
        conflicted, he noted it manually. When the document changed, he sometimes had to rebuild
        sections of the table from scratch.
      </p>

      <p>It wasn't a workflow. It was an act of endurance.</p>

      <hr />

      <h2>Why this happens in every organisation</h2>

      <p>
        Here's the thing: he wasn't doing it wrong. He was doing it the only way available to him.
      </p>

      <p>
        This is the standard in associations, federations, trade unions, and NGOs across Europe. Not
        because organisations are behind. Not because the people running these processes lack skill
        or rigour. But because the tools were never built for this specific need.
      </p>

      <p>
        Enterprise governance software — when it exists at all — is built for large institutions
        with the resources to deploy and maintain it. General-purpose tools like Word or Google Docs
        were designed for documents, not for amendment workflows. So organisations improvise. They
        build elaborate tables. They develop personal systems. They rely on the discipline and memory
        of one person — usually the one who built the table in the first place — to hold the whole
        thing together.
      </p>

      <p>
        It works. Until it doesn't. Until the volume grows, the deadline gets closer, and the person
        holding it all together is working at midnight trying to reconcile two conflicting versions
        of Article 7.
      </p>

      <hr />

      <h2>The moment that changes the question</h2>

      <p>
        I built my colleague a small local application to solve his immediate problem. It helped. But
        it couldn't manage external contributions, didn't support team collaboration, had no vote
        tracking, no audit trail. It solved one person's problem in one congress.
      </p>

      <p>
        That afternoon in my office, I stopped thinking about the software he'd asked for — the
        Commission's monolith — and started thinking about the actual problem underneath it.
      </p>

      <p>
        The problem isn't that organisations lack discipline. The problem is that the amendment
        process has always been treated as a document management task, when it is actually a
        structured collaboration workflow with very specific rules, sequences, and outputs.
      </p>

      <p>Once you see it that way, the solution becomes obvious.</p>

      <p>But that's a conversation for another post.</p>

      <hr />

      <p>
        <em>
          If this resonates with something you've experienced in your organisation, the waitlist for
          Amendly is open at{' '}
          <a href="https://amendly.eu" className="text-secondary hover:underline">
            amendly.eu
          </a>
          . No commitment — just a place to follow what we're building.
        </em>
      </p>

    </>
  )
}
