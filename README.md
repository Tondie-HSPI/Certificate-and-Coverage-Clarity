# Coverage Clarity

Coverage Clarity is an insurance document review tool for contracts, Certificates of Insurance (COIs), policies, and endorsement evidence.

It turns insurance requirements into structured review items, compares those requirements against uploaded evidence, and drafts a human-review email request for the insured's broker, insurance agent, or carrier representative.

## Background

This started as a vision from my Applied AI & Business Analytics program: insurance and
compliance teams spend too much time manually decoding contracts, COIs, and policies to
figure out what's actually required and what's missing. I spent months exploring the
problem, taking notes at conferences, and learning the tools, before building Compliance
Explained as a first working prototype. Coverage Clarity is where that thinking landed:
a more complete extraction, comparison, and decision-support workflow built end to end.

## Product Shape

- Frontend: Lovable or the existing Next.js app shell in this repo
- Backend: FastAPI COI review API in `backend/app`
- Deployment target: AWS through LeapStacks2 or another container-friendly path

## Core Workflow

`Contract + COI / policy / endorsements -> Extract -> Compare -> Review -> Email draft`

## Current Checks

- General Liability limits
- Umbrella / Excess limits
- Additional Insured parties and endorsement signals
- Waiver of Subrogation parties and endorsement signals
- Certificate Holder and additional coverage notes
- Management liability lines, including D&O, EPLI, Fiduciary, Crime/Fidelity, and Cyber Liability
- Cyber / Tech E&O component checks, including privacy, network security, breach response, PCI/payment card, media liability, ransomware/extortion, dependent business interruption, computer fraud, social engineering, and regulatory defense signals

## Architecture (RECKON-Aligned)

Coverage Clarity's backend follows the RECKON framework I use across my AI orchestration projects:

- **R — Request**: `input_layer/intake.py` builds initial state from the incoming request.
- **E — Extraction**: `extraction_layer/insurance_parser.py` parses contracts, COIs, and policies.
- **C — Context**: `obligation_modeling/modeler.py` builds structured obligations from extracted content.
- **K — Knowledge**: `governance/constraints.py` and `rules/*.yaml` apply domain rules and refusal logic.
- **O — Orchestration**: `state_engine/engine.py` assigns state across the review pipeline.
- **N — Next Best Action**: `decision_support/advisor.py` generates explanations and recommended next steps per item.

## Backend API

Run locally:

```powershell
.\start-backend.ps1
```

Default local API:

```text
http://127.0.0.1:8010
```

Health check:

```text
GET /health
```

Endpoints:

- `POST /api/coi-review` accepts pasted/structured text documents.
- `POST /api/coi-review-upload` accepts PDF, text, and Markdown uploads.
- Legacy aliases are also available: `POST /api/analyze` and `POST /api/analyze-upload`.

## Frontend

The existing Next.js app can remain as a project shell, but the production frontend may be built in Lovable. Use the API contract in:

```text
docs/LOVABLE_FRONTEND_API.md
```

## Deployment

- Dockerfile: `backend/Dockerfile`
- Container port: `8080`
- AWS / LeapStacks notes: `docs/AWS_LEAPSTACKS_LAUNCH.md`
- Lovable frontend contract: `docs/LOVABLE_FRONTEND_API.md`

## Boundary

Coverage Clarity is decision support only. It does not certify compliance, confirm coverage, bind insurance, or provide legal or insurance advice. All outputs require human review.
