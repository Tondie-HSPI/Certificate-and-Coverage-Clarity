"use client";

import { FormEvent, useMemo, useState } from "react";

type StartingDocument = "contract" | "coverage";

type DecisionItem = {
  obligation_type: string;
  requirement: string;
  evidence_requirement?: string | null;
  evidence_source?: string | null;
  source_excerpt: string;
  state: string;
  explanation: string;
  next_action: string;
};

type AnalysisResponse = {
  workflow_id: string;
  analysis_mode: string;
  overall_confidence: number;
  items: DecisionItem[];
  source_of_truth: {
    basis: string;
    document_name?: string;
  };
  email_draft?: {
    subject: string;
    body: string;
  } | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
const maxFileSize = 10 * 1024 * 1024;
const allowedExtensions = [".pdf", ".docx", ".txt"];
const stateLabels: Record<string, string> = {
  met: "Supported by evidence",
  missing: "Missing evidence",
  unmet: "Does not align",
  needs_review: "Needs review",
  unclear: "Unclear",
  not_extracted: "Not extracted",
};

export default function Home() {
  const [startingDocument, setStartingDocument] = useState<StartingDocument>("contract");
  const [file, setFile] = useState<File | null>(null);
  const [secondFile, setSecondFile] = useState<File | null>(null);
  const [requirementsText, setRequirementsText] = useState("");
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [emailRecipient, setEmailRecipient] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");

  const isCoverageReview = startingDocument === "coverage";
  const canAnalyze = useMemo(
    () => Boolean(
      file &&
      (!isCoverageReview || requirementsText.trim() || secondFile) &&
      !isAnalyzing,
    ),
    [file, isCoverageReview, requirementsText, secondFile, isAnalyzing],
  );

  function validateFile(selectedFile: File | null) {
    if (!selectedFile) return "";
    const extension = selectedFile.name.slice(selectedFile.name.lastIndexOf(".")).toLowerCase();
    if (!allowedExtensions.includes(extension)) return "Choose a PDF, DOCX, or TXT document.";
    if (selectedFile.size > maxFileSize) return "Choose a document smaller than 10 MB.";
    return "";
  }

  function chooseFile(selectedFile: File | null, target: "first" | "second") {
    const validationError = validateFile(selectedFile);
    setError(validationError);
    if (validationError) {
      if (target === "first") setFile(null);
      if (target === "second") setSecondFile(null);
      return;
    }
    if (target === "first") setFile(selectedFile);
    if (target === "second") setSecondFile(selectedFile);
    setResult(null);
  }

  function changeStartingDocument(value: StartingDocument) {
    setStartingDocument(value);
    setFile(null);
    setSecondFile(null);
    setRequirementsText("");
    setResult(null);
    setError("");
    setEmailRecipient("");
    setEmailSubject("");
    setEmailBody("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !canAnalyze) return;

    setError("");
    setResult(null);
    setIsAnalyzing(true);

    const form = new FormData();
    form.append("account_role", "reviewer");
    form.append("files", file);
    form.append("document_types", isCoverageReview ? "coi" : "contract");

    if (secondFile) {
      form.append("files", secondFile);
      form.append("document_types", isCoverageReview ? "contract" : "coi");
    }

    if (isCoverageReview && requirementsText.trim()) {
      form.append("requirements_text", requirementsText.trim());
      form.append("requirements_document_id", "manual-requirements");
    } else if (isCoverageReview && secondFile) {
      form.append("requirements_document_id", `1-${secondFile.name}`);
    } else {
      form.append("requirements_document_id", `0-${file.name}`);
    }

    try {
      const response = await fetch(`${apiUrl}/api/analyze-upload`, {
        method: "POST",
        body: form,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? payload.reason ?? "The document could not be analyzed.");
      }
      setResult(payload);
      setEmailRecipient("");
      setEmailSubject(payload.email_draft?.subject ?? "");
      setEmailBody(payload.email_draft?.body ?? "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The document could not be analyzed.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function openEmail() {
    const mailto = `mailto:${encodeURIComponent(emailRecipient.trim())}?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`;
    window.location.href = mailto;
  }

  return (
    <main className="appShell">
      <section className="hero">
        <div>
          <p className="eyebrow">Commercial insurance decision support</p>
          <h1>Certificate &amp; Coverage Clarity</h1>
          <p className="heroCopy">
            Start with the document you have. Get a clear review and a ready-to-check email for
            the right next step.
          </p>
        </div>
        <div className="heroPanel">
          <span>Source of truth</span>
          <strong>Requester requirements</strong>
          <p>The system extracts and compares evidence. You remain in control of every message.</p>
        </div>
      </section>

      <section className="demoNotice" aria-label="Public demonstration notice">
        <strong>Public portfolio demonstration</strong>
        <span>
          Use the synthetic sample files or de-identified documents only. Do not upload
          confidential, personal, or client information. Every result requires human review.
        </span>
      </section>

      <section className="panel intakePanel">
        <div className="sectionHeader">
          <div>
            <p className="eyebrow">New review</p>
            <h2>What document do you have?</h2>
            <p>Choose one path. You only need to upload one document to begin.</p>
          </div>
          <span className="badge">Human review required</span>
        </div>

        <aside className="samplePack" aria-labelledby="sample-pack-title">
          <div>
            <p className="eyebrow">Try the workflow</p>
            <h3 id="sample-pack-title">Download the sample documents</h3>
            <p>
              These synthetic files are safe to use. Download them, then upload the requirements
              first and the certificate as the optional second document.
            </p>
          </div>
          <div className="sampleLinks">
            <a href="/samples/requester-requirements.txt" download>
              Download requirements
            </a>
            <a href="/samples/sample-certificate.txt" download>
              Download certificate
            </a>
          </div>
        </aside>

        <div className="pathChoices" role="radiogroup" aria-label="Starting document">
          <button
            className={`pathChoice ${startingDocument === "contract" ? "selected" : ""}`}
            type="button"
            role="radio"
            aria-checked={startingDocument === "contract"}
            onClick={() => changeStartingDocument("contract")}
          >
            <strong>I have a contract</strong>
            <span>Extract the requirements and draft an email to my insurance agent.</span>
          </button>
          <button
            className={`pathChoice ${startingDocument === "coverage" ? "selected" : ""}`}
            type="button"
            role="radio"
            aria-checked={startingDocument === "coverage"}
            onClick={() => changeStartingDocument("coverage")}
          >
            <strong>I have coverage documents</strong>
            <span>Check a certificate or policy against the requester&apos;s requirements.</span>
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <label className={`uploadCard singleUpload ${file ? "hasFile" : ""}`}>
            <span className="stepNumber">1</span>
            <strong>{isCoverageReview ? "Certificate or policy" : "Contract or requirements"}</strong>
            <small>
              {isCoverageReview
                ? "Upload a certificate, policy excerpt, or endorsement"
                : "Upload a contract, insurance exhibit, checklist, or requirements list"}
            </small>
            <input
              key={startingDocument}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null, "first")}
            />
            <span className="fileName">{file?.name ?? "Choose one document"}</span>
          </label>

          <div className="optionalDocument">
            <div className="optionalHeading">
              <span className="stepNumber">2</span>
              <div>
                <strong>Add a second document</strong>
                <span>
                  Optional. Add it to see whether the coverage aligns with the requester&apos;s
                  requirements.
                </span>
              </div>
            </div>
            <label className={`compactUpload ${secondFile ? "hasFile" : ""}`}>
              <input
                key={`second-${startingDocument}`}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(event) => chooseFile(event.target.files?.[0] ?? null, "second")}
              />
              {secondFile?.name ??
                `Choose ${isCoverageReview ? "contract or requirements" : "certificate or policy"}`}
            </label>
          </div>

          {isCoverageReview && !secondFile && (
            <label className="requirementsField">
              <strong>Or enter the requirements</strong>
              <span>
                Paste or enter the requester&apos;s stated requirements. These become the
                comparison baseline.
              </span>
              <textarea
                value={requirementsText}
                onChange={(event) => setRequirementsText(event.target.value)}
                placeholder="Example: General liability of $1,000,000 per occurrence, additional insured status, and waiver of subrogation."
                rows={5}
              />
            </label>
          )}

          <div className="sourceConfirmation">
            <strong>What happens next</strong>
            <span>
              {isCoverageReview
                ? "We compare the coverage evidence with the uploaded or entered requirements. Missing items create an agent email. Supported items create a requester email."
                : secondFile
                  ? "We compare the certificate or policy against the contract requirements and prepare the appropriate email."
                  : "We extract the requirements and prepare an email you can review before sending to your insurance agent."}
            </span>
          </div>

          <button className="primaryButton" type="submit" disabled={!canAnalyze}>
            {isAnalyzing ? "Reviewing document..." : "Review document"}
          </button>
          <p className="uploadLimit">Up to two files. PDF, DOCX, or TXT. Maximum 10 MB each.</p>
        </form>

        {error && <div className="errorMessage" role="alert">{error}</div>}
      </section>

      {result && (
        <section className="panel resultsPanel" aria-live="polite">
          <div className="sectionHeader">
            <div>
              <p className="eyebrow">Review results</p>
              <h2>{result.items.length} review item{result.items.length === 1 ? "" : "s"}</h2>
            </div>
            <span className="badge">Insurance representative verification required</span>
          </div>

          <div className="resultLegend" aria-label="Result status guide">
            <span><i className="legendDot met" />Supported by evidence</span>
            <span><i className="legendDot missing" />Missing evidence</span>
            <span><i className="legendDot unmet" />Does not align</span>
            <span><i className="legendDot needsreview" />Needs review</span>
          </div>

          <div className="sourceRecord">
            <span>Source of truth</span>
            <strong>{result.source_of_truth.basis}</strong>
            <small>{result.source_of_truth.document_name}</small>
          </div>

          {result.items.length ? (
            <div className="reviewTable">
              {result.items.map((item) => (
                <article className="reviewRow" key={`${item.obligation_type}-${item.state}`}>
                  <div>
                    <strong>{item.obligation_type}</strong>
                    <span className={`status ${item.state.replaceAll("_", "")}`}>
                      {stateLabels[item.state] ?? item.state.replaceAll("_", " ")}
                    </span>
                  </div>
                  <div>
                    <span className="detailLabel">Requester requirement</span>
                    <p>{item.requirement}</p>
                    <span className="detailLabel">Evidence reviewed</span>
                    <p>{item.evidence_requirement || item.source_excerpt || "No matching evidence was extracted."}</p>
                    {item.evidence_source && <small>Source: {item.evidence_source}</small>}
                  </div>
                  <div>
                    <span className="detailLabel">Review explanation</span>
                    <p>{item.explanation}</p>
                    <p className="action">{item.next_action}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="emptyResult">
              <strong>No specific insurance requirements were found.</strong>
              <p>Review the document or add more detail before relying on the result.</p>
            </div>
          )}

          {result.email_draft && (
            <div className="emailDraft">
              <p className="eyebrow">Email draft for your review</p>
              <div className="sendChecklist">
                <strong>Before sending</strong>
                <span>Attach the requester&apos;s requirements.</span>
                <span>Verify the extracted certificate holder name and address.</span>
                <span>Confirm the requester-required wording. “None” means none was stated.</span>
              </div>
              <div className="emailFields">
                <label>
                  <strong>Recipient</strong>
                  <input
                    type="email"
                    value={emailRecipient}
                    onChange={(event) => setEmailRecipient(event.target.value)}
                    placeholder="agent@example.com"
                  />
                </label>
                <label>
                  <strong>Subject</strong>
                  <input
                    type="text"
                    value={emailSubject}
                    onChange={(event) => setEmailSubject(event.target.value)}
                  />
                </label>
                <label>
                  <strong>Message</strong>
                  <textarea
                    rows={14}
                    value={emailBody}
                    onChange={(event) => setEmailBody(event.target.value)}
                  />
                </label>
              </div>
              <button className="primaryButton" type="button" onClick={openEmail}>
                Open in email
              </button>
              <p className="emailNote">
                This opens a draft in your email application. It does not send automatically.
                Attachments must be added manually.
              </p>
            </div>
          )}
        </section>
      )}

      <section className="panel disclaimer">
        <p className="eyebrow">Review boundary</p>
        <p>
          This tool supports document review. It does not confirm coverage, certify compliance,
          bind insurance, or provide legal or insurance advice.
        </p>
      </section>
    </main>
  );
}
