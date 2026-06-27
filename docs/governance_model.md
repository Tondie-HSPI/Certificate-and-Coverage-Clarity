# Governance Model

Coverage Clarity uses a layered governance model for insurance document review. The goal is to demonstrate that AI-assisted workflows can support review-heavy operations without allowing generative reasoning to control business decisions.

## Core Principle

Deterministic controls and generative reasoning are separated:

- **LLM / language reasoning:** summarization, explanation, drafting, interpretation, and tone adaptation.
- **Application control:** validation logic, thresholds, routing, refusal triggers, escalation, and state management.
- **Data grounding:** uploaded documents, source excerpts, structured records, and retrieved context.
- **Tools / deterministic execution:** rule checks, limit comparison, schema validation, and repeatable calculations.
- **Human review:** final accountability for carrier-facing, compliance-facing, or coverage-related decisions.

## Governance Rules

1. Exact checks and calculations are handled by deterministic rules, not language generation.
2. Outputs must use structured schemas so they can feed review packets, dashboards, or audit trails.
3. Missing, unmet, unclear, and low-grounding outputs are routed to human review.
4. The system may draft follow-up language, but it may not approve, bind, certify, or confirm coverage.
5. Prompt-injection style instructions inside uploaded documents are refused.
6. Unsupported document types and out-of-scope topics are refused.
7. Outputs are checked for prohibited overconfident language before being returned.

## Failure Modes Covered

- Hallucination: constrained by source-grounded fields and prohibited-phrase checks.
- Retrieval or evidence mismatch: handled through deterministic comparison states.
- Data incompleteness: surfaced as missing information or needs-review items.
- Overconfidence: review states receive mandatory human-review language.
- Workflow drift: outputs must stay inside the approved decision state machine.

## Human Accountability

Coverage Clarity is decision support only. A qualified human reviewer owns the final decision before any carrier-facing, client-facing, legal, compliance, or coverage-related use.
