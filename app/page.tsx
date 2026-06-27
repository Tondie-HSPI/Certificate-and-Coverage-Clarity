const metrics = [
  { label: "Review states", value: "Met / Unmet / Missing" },
  { label: "Evidence types", value: "Contract, COI, Policy, Endorsement" },
  { label: "Human review", value: "Required for all outputs" },
  { label: "Backend", value: "FastAPI + deterministic rules" }
];

const workflow = [
  "Upload or paste contract and evidence text",
  "Extract requirements, limits, parties, and endorsement signals",
  "Compare required coverage against available evidence",
  "Generate review items, gap flags, and an email draft"
];

const reviewItems = [
  {
    type: "General Liability",
    status: "Met",
    detail: "$1M occurrence / $2M aggregate shown in evidence.",
    action: "No immediate action needed."
  },
  {
    type: "Additional Insured",
    status: "Needs review",
    detail: "Certificate wording references AI, but endorsement evidence is not confirmed.",
    action: "Request supporting endorsement or corrected certificate."
  },
  {
    type: "Waiver of Subrogation",
    status: "Missing",
    detail: "Contract requires WOS; evidence did not show matching support.",
    action: "Request revised COI or supporting endorsement evidence."
  }
];

export default function Home() {
  return (
    <main className="appShell">
      <section className="hero">
        <div>
          <p className="eyebrow">Commercial insurance decision support</p>
          <h1>Coverage Clarity</h1>
          <p className="heroCopy">
            AI-assisted review for contracts, COIs, policies, and endorsement evidence. The system
            structures review items, identifies gaps, and prepares follow-up language while keeping
            every output human-reviewed.
          </p>
        </div>
        <div className="heroPanel">
          <span>Prototype boundary</span>
          <strong>Decision support only</strong>
          <p>No coverage confirmation, binding, legal advice, or automated approval.</p>
        </div>
      </section>

      <section className="metricGrid" aria-label="Project metrics">
        {metrics.map((metric) => (
          <article key={metric.label} className="metricCard">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </article>
        ))}
      </section>

      <section className="twoColumn">
        <article className="panel">
          <p className="eyebrow">Workflow</p>
          <h2>From requirement text to review-ready output</h2>
          <ol className="steps">
            {workflow.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </article>

        <article className="panel">
          <p className="eyebrow">Why it matters</p>
          <h2>Built for review-heavy operations</h2>
          <p>
            Insurance document review often depends on details that are easy to miss: limits,
            parties, endorsement wording, certificate holder language, and whether evidence actually
            supports the contract requirement.
          </p>
          <p>
            Coverage Clarity turns those details into structured, auditable outputs so a reviewer
            can see what was found, what is missing, and what needs follow-up.
          </p>
        </article>
      </section>

      <section className="panel outputPanel">
        <div className="sectionHeader">
          <div>
            <p className="eyebrow">Sample output</p>
            <h2>Human-reviewed decision items</h2>
          </div>
          <span className="badge">Synthetic sample</span>
        </div>
        <div className="reviewTable">
          {reviewItems.map((item) => (
            <article key={item.type} className="reviewRow">
              <div>
                <strong>{item.type}</strong>
                <span className={`status ${item.status.replace(" ", "").toLowerCase()}`}>
                  {item.status}
                </span>
              </div>
              <p>{item.detail}</p>
              <p className="action">{item.action}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel disclaimer">
        <p className="eyebrow">Human-in-the-loop boundary</p>
        <p>
          This is an independent portfolio prototype using mock data and synthetic examples. It does
          not include employer data, client data, proprietary workflows, or internal company tools.
          Outputs are designed to support review, not replace professional judgment.
        </p>
      </section>
    </main>
  );
}
