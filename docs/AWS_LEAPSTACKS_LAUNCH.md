# AWS / LeapStacks Launch Notes

Goal: run the Coverage Clarity backend as a standalone API in AWS, then connect a Lovable
frontend to it.

LeapStacks2 describes itself as an AWS launchpad with CloudFormation deployment,
GitHub export/import workflows, and external Lovable app hosting. Use LeapStacks
for the AWS hosting path and keep this repo as the backend source of truth.

## Recommended Architecture

```text
Lovable frontend
  -> HTTPS API URL
  -> Coverage Clarity FastAPI backend
  -> Embedded PDF/DOCX text extraction
  -> Amazon Textract fallback for image-based PDFs
  -> Deterministic comparison and email draft generation
```

For the backend, use a container-friendly AWS target such as App Runner, ECS, or
any LeapStacks external-app/GitHub deployment route that supports a Python web
service.

## Backend Build

Docker context:

```text
backend/
```

Dockerfile:

```text
backend/Dockerfile
```

Container port:

```text
8080
```

Health check:

```text
GET /health
```

Start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Environment Variables

```text
COVERAGE_CLARITY_APP_NAME=Coverage Clarity API
COVERAGE_CLARITY_APP_ENV=production
COVERAGE_CLARITY_CORS_ALLOW_ORIGINS=["https://your-lovable-domain.example"]
COVERAGE_CLARITY_TEXTRACT_BUCKET=your-private-temporary-bucket
```

During early testing, `COVERAGE_CLARITY_CORS_ALLOW_ORIGINS=["*"]` is acceptable, but narrow
it to the Lovable production URL before sharing with real users.

## LeapStacks Sequence

1. Push this backend repo to GitHub.
2. Deploy LeapStacks2 into your AWS account using its CloudFormation installer.
3. Use the LeapStacks GitHub/external app hosting path that supports a backend
   service or container.
4. Point it at the `backend/` folder and expose port `8080`.
5. Confirm `/health` returns `{"status":"ok"}`.
6. Put the deployed API URL into the Lovable frontend as the API base URL.
7. Test `/api/coi-review` with pasted text.
8. Test `/api/coi-review-upload` with a sample contract PDF and COI PDF.

## Launch Checklist

- CORS restricted to Lovable frontend domain
- API URL uses HTTPS
- Upload size limits configured at the hosting layer
- No sensitive sample documents committed
- Temporary Textract bucket is encrypted, private, and has a one-day lifecycle rule
- Clear human-review disclaimer shown in the frontend
- Email drafts are editable and not sent automatically
- CloudWatch or equivalent logs enabled
- Cost controls / cleanup rules reviewed in LeapStacks
