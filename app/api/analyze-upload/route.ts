const backendApiUrl = (
  process.env.COVERAGE_CLARITY_BACKEND_API_URL
  ?? "https://c3jm2q3x3woezmtr76nsinjuti0phibv.lambda-url.us-east-2.on.aws"
).replace(/\/$/, "");

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(request: Request) {
  try {
    const contentType = request.headers.get("content-type");
    if (!contentType?.toLowerCase().startsWith("multipart/form-data")) {
      return Response.json({ detail: "Upload one or two documents." }, { status: 400 });
    }

    const response = await fetch(`${backendApiUrl}/api/analyze-upload`, {
      method: "POST",
      headers: { "content-type": contentType },
      body: request.body,
      cache: "no-store",
      duplex: "half",
    } as RequestInit & { duplex: "half" });

    return new Response(response.body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch (error) {
    console.error("Coverage Clarity backend request failed", error);
    return Response.json(
      { detail: "The review service is temporarily unavailable. Please try again." },
      { status: 502 },
    );
  }
}
