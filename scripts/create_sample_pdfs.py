from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "pdf"

NAVY = colors.HexColor("#102033")
BLUE = colors.HexColor("#2563EB")
TEAL = colors.HexColor("#0F766E")
PALE_BLUE = colors.HexColor("#EFF6FF")
PALE_TEAL = colors.HexColor("#F0FDFA")
LINE = colors.HexColor("#D9E2EF")
MUTED = colors.HexColor("#5F6F85")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SampleTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "SampleSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "SampleSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=BLUE,
            spaceBefore=10,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "SampleBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=NAVY,
        ),
        "small": ParagraphStyle(
            "SampleSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
        ),
        "table_header": ParagraphStyle(
            "SampleTableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "banner": ParagraphStyle(
            "SampleBanner",
            parent=base["BodyText"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.white,
        ),
    }


def page_header(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 0.38 * inch, width, 0.38 * inch, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(0.62 * inch, height - 0.25 * inch, "PATHWAY ILLUMINATION")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 0.62 * inch, height - 0.25 * inch, "PUBLIC DEMONSTRATION SAMPLE")
    canvas.setStrokeColor(LINE)
    canvas.line(0.62 * inch, 0.53 * inch, width - 0.62 * inch, 0.53 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(0.62 * inch, 0.32 * inch, "For product demonstration only. Not an issued insurance document.")
    canvas.drawRightString(width - 0.62 * inch, 0.32 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_requirements(path: Path):
    s = styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.62 * inch,
        rightMargin=0.62 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.72 * inch,
        title="Public Sample Requester Insurance Requirements",
        author="Pathway Illumination",
    )
    story = [
        Spacer(1, 0.08 * inch),
        Paragraph("Requester Insurance Requirements", s["title"]),
        Paragraph(
            "A publicly available sample created to demonstrate requirement extraction and certificate comparison.",
            s["subtitle"],
        ),
    ]

    details = [
        [Paragraph("Certificate holder", s["small"]), Paragraph("Northbridge Development LLC", s["body"])],
        [Paragraph("Address", s["small"]), Paragraph("100 Main Street, Rochester, NY 14604", s["body"])],
        [Paragraph("Requester-required wording", s["small"]), Paragraph("None", s["body"])],
    ]
    table = Table(details, colWidths=[1.75 * inch, 4.65 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([table, Spacer(1, 0.16 * inch), Paragraph("Required coverage", s["section"])])

    rows = [
        [Paragraph("Requirement", s["table_header"]), Paragraph("Requested evidence", s["table_header"])],
        [
            Paragraph("Commercial General Liability", s["body"]),
            Paragraph("$1,000,000 each occurrence and $2,000,000 general aggregate. Coverage must apply on an occurrence basis.", s["body"]),
        ],
        [
            Paragraph("Additional Insured", s["body"]),
            Paragraph("Northbridge Development LLC must be included as an additional insured by endorsement.", s["body"]),
        ],
        [
            Paragraph("Waiver of Subrogation", s["body"]),
            Paragraph("A waiver of subrogation in favor of Northbridge Development LLC is required where permitted by law.", s["body"]),
        ],
        [
            Paragraph("Umbrella or Excess Liability", s["body"]),
            Paragraph("A limit of not less than $5,000,000 is required.", s["body"]),
        ],
    ]
    coverage_table = Table(rows, colWidths=[2.0 * inch, 4.4 * inch], repeatRows=1)
    coverage_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend(
        [
            coverage_table,
            Spacer(1, 0.18 * inch),
            Paragraph(
                "Use this document as the source of truth when testing Certificate &amp; Coverage Clarity.",
                s["body"],
            ),
        ]
    )
    doc.build(story, onFirstPage=page_header, onLaterPages=page_header)


def build_certificate(path: Path):
    s = styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.62 * inch,
        rightMargin=0.62 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.72 * inch,
        title="Public Sample Certificate of Liability Insurance",
        author="Pathway Illumination",
    )
    story = [
        Spacer(1, 0.08 * inch),
        Paragraph("Sample Certificate of Liability Insurance", s["title"]),
        Paragraph(
            "A publicly available sample created for document-comparison testing. This is not an ACORD form or evidence of active coverage.",
            s["subtitle"],
        ),
    ]

    parties = [
        [Paragraph("Producer", s["small"]), Paragraph("Lakeside Risk Partners", s["body"]), Paragraph("Insured", s["small"]), Paragraph("Summit Building Services LLC", s["body"])],
        [Paragraph("Policy period", s["small"]), Paragraph("01/01/2026 to 01/01/2027", s["body"]), Paragraph("Certificate date", s["small"]), Paragraph("06/15/2026", s["body"])],
    ]
    parties_table = Table(parties, colWidths=[0.85 * inch, 2.35 * inch, 0.85 * inch, 2.35 * inch])
    parties_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([parties_table, Spacer(1, 0.16 * inch), Paragraph("Coverage summary", s["section"])])

    rows = [
        [Paragraph("Coverage", s["table_header"]), Paragraph("Policy number", s["table_header"]), Paragraph("Limits shown", s["table_header"])],
        [Paragraph("Commercial General Liability", s["body"]), Paragraph("CGL-2026-1042", s["body"]), Paragraph("$1,000,000 each occurrence<br/>$2,000,000 general aggregate", s["body"])],
        [Paragraph("Umbrella Liability", s["body"]), Paragraph("UMB-2026-1042", s["body"]), Paragraph("$5,000,000 each occurrence<br/>$5,000,000 aggregate", s["body"])],
    ]
    coverage_table = Table(rows, colWidths=[2.35 * inch, 1.55 * inch, 2.5 * inch], repeatRows=1)
    coverage_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend(
        [
            coverage_table,
            Paragraph("Endorsement information", s["section"]),
            Paragraph(
                "Northbridge Development LLC is shown as an additional insured for ongoing operations. A separate waiver of subrogation endorsement is not shown in this sample.",
                s["body"],
            ),
            Paragraph("Certificate holder", s["section"]),
        ]
    )
    holder = Table(
        [[Paragraph("Northbridge Development LLC<br/>100 Main Street<br/>Rochester, NY 14604", s["body"]) ]],
        colWidths=[6.4 * inch],
    )
    holder.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 0.8, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([holder, Spacer(1, 0.14 * inch), Paragraph("Special wording: None", s["body"])])
    doc.build(story, onFirstPage=page_header, onLaterPages=page_header)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "requester-requirements-sample.pdf": build_requirements,
        "certificate-sample.pdf": build_certificate,
    }
    for filename, builder in artifacts.items():
        output_path = OUTPUT_DIR / filename
        builder(output_path)


if __name__ == "__main__":
    main()
