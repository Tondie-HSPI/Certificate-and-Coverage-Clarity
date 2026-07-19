import { NextResponse } from "next/server";

type Finding = {
  obligation_type: string;
  requirement: string;
  evidence_requirement: string | null;
  evidence_source: string | null;
  source_excerpt: string;
  state: "met" | "missing" | "unmet" | "needs_review";
  explanation: string;
  next_action: string;
};

const rules = [
  { name: "General Liability", terms: ["general liability", "commercial general liability", "each occurrence"] },
  { name: "Additional Insured", terms: ["additional insured"] },
  { name: "Waiver of Subrogation", terms: ["waiver of subrogation"] },
  { name: "Umbrella / Excess", terms: ["umbrella", "excess liability"] },
  { name: "Automobile Liability", terms: ["automobile liability", "auto liability"] },
  { name: "Workers Compensation", terms: ["workers compensation", "workers' compensation"] },
  { name: "Certificate Holder", terms: ["certificate holder"] },
] as const;

function nearbyText(text: string, terms: readonly string[]) {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return lines.find((line) => terms.some((term) => line.toLowerCase().includes(term))) ?? "";
}

function hasNegation(text: string, term: string) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\b(?:no|without)\\s+${escaped}\\b|${escaped}.{0,24}\\bnot\\s+(?:required|included|shown|provided)\\b`, "i").test(text);
}

function extractAmount(text: string) {
  const match = text.match(/\$[\d,]+(?:\.\d+)?\s*(?:million|thousand|m)?|\b\d+(?:\.\d+)?\s*million\b/i);
  if (!match) return null;
  const normalized = match[0].toLowerCase().replaceAll("$", "").replaceAll(",", "").trim();
  const multiplier = normalized.includes("million") || normalized.endsWith("m")
    ? 1_000_000
    : normalized.includes("thousand") ? 1_000 : 1;
  return Number.parseFloat(normalized.replace(/million|thousand|m/g, "").trim()) * multiplier;
}

function labelRequirement(name: string, excerpt: string) {
  const amount = extractAmount(excerpt);
  if (name === "General Liability" && amount) return `$${amount.toLocaleString()} per occurrence`;
  if (name === "Umbrella / Excess" && amount) return `$${amount.toLocaleString()} umbrella / excess`;
  if (name === "Certificate Holder") {
    return excerpt.replace(/^.*certificate holder(?: name)?\s*:\s*/i, "").trim() || "Certificate holder required";
  }
  return `${name} required`;
}

function compare(requirements: string, evidence: string, requirementName: string, evidenceName: string) {
  const findings: Finding[] = [];

  for (const rule of rules) {
    const requirementExcerpt = nearbyText(requirements, rule.terms);
    if (!requirementExcerpt || rule.terms.some((term) => hasNegation(requirementExcerpt, term))) continue;

    const evidenceExcerpt = nearbyText(evidence, rule.terms);
    const requirement = labelRequirement(rule.name, requirementExcerpt);
    let state: Finding["state"] = "missing";

    if (evidenceExcerpt && !rule.terms.some((term) => hasNegation(evidenceExcerpt, term))) {
      const requiredAmount = extractAmount(requirementExcerpt);
      const evidenceAmount = extractAmount(evidenceExcerpt);
      state = requiredAmount && (!evidenceAmount || evidenceAmount < requiredAmount) ? "unmet" : "met";
    }

    findings.push({
      obligation_type: rule.name,
      requirement,
      evidence_requirement: evidenceExcerpt ? labelRequirement(rule.name, evidenceExcerpt) : null,
      evidence_source: evidenceExcerpt ? evidenceName : null,
      source_excerpt: evidenceExcerpt
        ? `Requirement: ${requirementExcerpt}\nEvidence: ${evidenceExcerpt}`
        : `Requirement: ${requirementExcerpt}`,
      state,
      explanation: state === "met"
        ? "The uploaded evidence supports this requester requirement."
        : state === "unmet"
          ? "Evidence was found, but it does not appear to meet the stated requirement."
          : "The requester requires this item, but matching evidence was not found.",
      next_action: state === "met"
        ? "Ask the requester to confirm acceptance."
        : "Ask the insurance representative to confirm coverage and provide corrected evidence.",
    });
  }

  return findings.length ? findings : [{
    obligation_type: "Document review",
    requirement: "Confirm the requester's insurance requirements",
    evidence_requirement: null,
    evidence_source: null,
    source_excerpt: requirements.slice(0, 500),
    state: "needs_review",
    explanation: "The prototype could not identify a supported requirement from the supplied text.",
    next_action: "Review the source document and confirm the requirements with the requester.",
  }];
}

function extractCertificateDetails(text: string) {
  const holder = text.match(/certificate holder(?: name)?\s*:\s*([^\r\n]+)/i)?.[1]?.trim() ?? "Not identified";
  const address = text.match(/(?:certificate holder address|holder address|address)\s*:\s*([^\r\n]+)/i)?.[1]?.trim() ?? "Not identified";
  const wording = text.match(/(?:required wording|special wording|requester-required wording)\s*:\s*([^\r\n]+)/i)?.[1]?.trim() ?? "Not identified. Confirm with requester.";
  return { holder, address, wording };
}

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const files = form.getAll("files").filter((value): value is File => value instanceof File);
    if (!files.length || files.length > 2) {
      return NextResponse.json({ detail: "Upload one or two documents." }, { status: 400 });
    }

    for (const file of files) {
      if (file.size > 10 * 1024 * 1024) {
        return NextResponse.json({ detail: `${file.name} must be smaller than 10 MB.` }, { status: 413 });
      }
      if (!file.name.toLowerCase().endsWith(".txt")) {
        return NextResponse.json({
          detail: "This public prototype currently analyzes TXT files. Download the synthetic samples above to test the complete workflow.",
        }, { status: 400 });
      }
    }

    const types = form.getAll("document_types").map(String);
    const texts = await Promise.all(files.map((file) => file.text()));
    const enteredRequirements = String(form.get("requirements_text") ?? "").trim();
    const contractIndex = types.findIndex((type) => type === "contract");
    const evidenceIndex = types.findIndex((type) => type !== "contract");
    const requirementsText = enteredRequirements || (contractIndex >= 0 ? texts[contractIndex] : texts[0]);
    const evidenceText = evidenceIndex >= 0 ? texts[evidenceIndex] : "";
    const requirementName = enteredRequirements ? "Confirmed requester requirements" : files[contractIndex >= 0 ? contractIndex : 0].name;
    const evidenceName = evidenceIndex >= 0 ? files[evidenceIndex].name : "";
    const items = evidenceText
      ? compare(requirementsText, evidenceText, requirementName, evidenceName)
      : compare(requirementsText, "", requirementName, "");
    const details = extractCertificateDetails(requirementsText);
    const needsAction = items.some((item) => item.state !== "met");
    const subject = needsAction
      ? "Insurance requirements requiring confirmation"
      : "Certificate review against requester requirements";
    const body = needsAction
      ? `Hello,\n\nPlease review the attached requester requirements and confirm the items below. The requester requirements should remain attached as the source of truth.\n\n${items.filter((item) => item.state !== "met").map((item) => `• ${item.obligation_type}: ${item.requirement}`).join("\n")}\n\nCertificate holder: ${details.holder}\nCertificate holder address: ${details.address}\nWording required by requester: ${details.wording}\n\nPlease confirm the coverage, forms, and endorsements before issuing revised evidence.\n\nThank you.`
      : `Hello,\n\nThe uploaded certificate was reviewed against the requester requirements and evidence was found for each identified item.\n\nCertificate holder: ${details.holder}\nCertificate holder address: ${details.address}\nWording required by requester: ${details.wording}\n\nPlease complete your own review and confirm acceptance.\n\nThank you.`;

    return NextResponse.json({
      workflow_id: crypto.randomUUID(),
      analysis_mode: evidenceText ? "comparison" : "requirements_extraction",
      overall_confidence: 0,
      items,
      source_of_truth: { basis: "Requirements provided by the certificate requester", document_name: requirementName },
      email_draft: { subject, body },
    });
  } catch {
    return NextResponse.json({ detail: "The document could not be analyzed." }, { status: 500 });
  }
}
