/**
 * Blog post: "Managing amendments in NGOs: why manual tools are reaching their limits"
 *
 * Authoring guide:
 *   <h2>      Section headings
 *   <p>       Paragraphs
 *   <em>      Italic
 *   <strong>  Bold
 *   <hr />    Section break
 *   <a href="...">  Links
 */
export default function Post() {
  return (
    <>
      <p>In the vast majority of associations, trade unions, and NGOs across Europe, amendment management still relies on two tools: a Word table and an email inbox. This is not a lack of rigour. It is simply that no affordable, purpose-built tool has ever existed for this specific need.</p>

      <p>This article explains why manual amendment processes reach their limits, what warning signs to watch for, and what alternatives exist today for organisations of a human scale.</p>

      <hr />

      <h2>What is an amendment process in an organisation?</h2>

      <p>An amendment process is the formal procedure by which members of an organisation propose modifications to a reference text — statutes, internal rules, congress resolutions, action programmes — before it is submitted to a vote at a general assembly or congress.</p>

      <p>The typical process includes: distributing the base text to members, collecting amendments within a set deadline, centralising them, reviewing them for admissibility and conflicts, presenting them to delegates, and finally consolidating the adopted amendments into the final text.</p>

      <p>It is a structured workflow with precise rules — and yet, in most organisations, it is managed as a formatting exercise in a word processor.</p>

      <hr />

      <h2>Why Word and email are no longer enough</h2>

      <p>Manual amendment management works up to a certain threshold. Below twenty or so amendments submitted by a handful of delegates, a well-maintained Word table remains manageable. Beyond that, problems accumulate quickly.</p>

      <p><strong>Traceability breaks down.</strong> When amendments arrive by email, it becomes difficult to guarantee that none were missed, that the version received is the latest, or that the status of each amendment is up to date. The audit trail depends entirely on one person's memory.</p>

      <p><strong>Conflict detection is manual.</strong> Two amendments targeting the same article may contradict each other. Without a dedicated tool, the responsible person must compare them visually, one by one.</p>

      <p><strong>Consolidation is a high-risk operation.</strong> Integrating adopted amendments into the final text, in the correct order, without introducing errors, is a painstaking task and a frequent source of omissions and inconsistencies.</p>

      <p><strong>Transparency is limited.</strong> Members do not know the status of their amendments. They cannot see what other delegates have proposed. The process remains opaque until the plenary session.</p>

      <hr />

      <h2>The organisations most affected</h2>

      <p>This problem is particularly acute in organisations whose governance depends on founding texts that are periodically revised.</p>

      <p><strong>Trade unions and professional organisations</strong> revise their statutes and bylaws at congresses that are often prepared over several months, with hundreds of delegates able to submit amendments.</p>

      <p><strong>Associations (loi 1901, ASBL/VZW, eingetragener Verein)</strong> amend their statutes at extraordinary general meetings, a process often managed by volunteers without specific document management expertise.</p>

      <p><strong>NGOs and European federations</strong> operate multilingually, with members across several countries, adding a layer of complexity to email-based exchanges.</p>

      <p><strong>Political parties and civic movements</strong> prepare programmes and motions with large numbers of delegates under tight deadlines.</p>

      <hr />

      <h2>What solutions exist today?</h2>

      <p>The market for amendment management tools falls into three categories.</p>

      <p><strong>Heavy institutional software</strong> — used by the European Parliament, some national parliaments, and large international institutions. These tools require dedicated infrastructure, IT teams, and budgets well beyond the reach of a standard-sized organisation.</p>

      <p><strong>Generic tools</strong> — Google Docs, Notion, or collaborative wikis can be repurposed for amendment management, but they lack native diff, voting, or consolidation features. They shift the problem without solving it.</p>

      <p><strong>Accessible dedicated platforms</strong> — this is the emerging segment. <a href="https://amendly.eu" className="text-secondary hover:underline">Amendly</a> is built specifically for this use case: structured amendment submission, automatic word-level diffs, per-amendment reactions and comments, one-click consolidation, and export to Word and PDF. It targets associations, trade unions, NGOs, and federations that need professional amendment workflow tooling without heavy infrastructure, starting at €9/month with a 7-day free trial.</p>

      <hr />

      <h2>What a good amendment management tool must do</h2>

      <p>Whatever solution you choose, a tool suited to amendment management must meet these fundamental criteria.</p>

      <p><strong>Structured submission.</strong> Each amendment must include at minimum the original text being targeted, the proposed replacement text, and the justification. A free-form email does not guarantee this structure.</p>

      <p><strong>Diff visualisation.</strong> The difference between the original and proposed text must be displayed automatically, at the word level, so reviewers immediately see what changes and why.</p>

      <p><strong>Traceability and audit trail.</strong> Each amendment must have a clear status (submitted, under review, accepted, rejected) and a queryable history.</p>

      <p><strong>Automated consolidation.</strong> The final text, with all adopted amendments integrated in the correct order, must be generatable without manual intervention.</p>

      <p><strong>Accessibility for external contributors.</strong> Delegates or members external to the organisation must be able to submit amendments without creating an account or mastering a complex tool.</p>

      <hr />

      <p>
        <em><a href="https://amendly.eu" className="text-secondary hover:underline">Amendly</a> is available with a free 7-day trial, no credit card required.</em>
      </p>
    </>
  )
}
