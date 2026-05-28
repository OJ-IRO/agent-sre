"""One-off generator for VIDEO_SCRIPT.pdf — the spoken script for the 3-minute
demo video, formatted for printing or on-screen reference while recording.

Run:  uv run --with reportlab python scripts/make_video_script_pdf.py
Outputs: VIDEO_SCRIPT.pdf in the project root.
"""
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    HRFlowable,
)


SCRIPT_PARAGRAPHS = [
    "Today's AI agents are everywhere — handling customer service, processing claims, even giving medical advice. But there's a problem nobody talks about: they fail in production constantly, and most companies don't catch it.",
    "A single customer-facing AI makes mistakes thousands of times a day. Some are harmless. But others — hallucinated flight times, leaked customer phone numbers, refused valid refunds — those cost real money and real trust.",
    "The current solution is to hire engineers to find and fix these failures. They read thousands of trace logs, write test cases, rewrite the AI's instructions, validate, deploy. It takes days. And most companies don't even catch the failures until customers complain.",
    "We built Agent SRE to solve this problem. And this isn't just theory — it's real, working code, deployed on Google Cloud, that just lifted an AI agent's safety score from 17% to 100% in five minutes, without any human in the loop.",
    "Our solution pairs an autonomous reliability layer with the production AI it watches.",
    "The first component is the <b>target agent</b> — any customer-facing AI. Our demo uses a travel concierge for the 2026 tournament, but it could be any AI: banking, healthcare, retail. The point is the same. The AI is talking to real people, making real mistakes.",
    "The second component is <b>Agent SRE</b> — an AI whose only job is monitoring and improving other AIs. It runs continuously, observing every conversation through Arize Phoenix.",
    "Here's how it works in practice. Agent SRE pulls recent production traces and clusters them into failure patterns. In our demo, it found unauthorized PII disclosure — the agent was sharing customer bookings with anyone who asked.",
    "Then it generated its own adversarial test suite — ten cases that exercise the exact failure — and wrote them into a Phoenix dataset for anyone to inspect.",
    "Next, it drafted a prompt fix with a multilingual identity-verification protocol, and validated it in real time. Before: one of six privacy probes refused. After: six of six. An 83-point improvement.",
    "When that delta cleared its safety threshold, Agent SRE shipped the fix and wrote its own postmortem. And it kept watching — a drift check confirmed the fix was holding.",
    "The economics matter. A reliability engineer costs two hundred thousand dollars a year and can babysit two or three agents at most. Agent SRE replaces that headcount — autonomously, across any number of production AIs.",
    "And Agent SRE isn't limited to customer service. The same loop applies anywhere an AI is making decisions: catching hallucinations in a banking bot, missed symptoms in healthcare triage, biased screenings in recruiting. Swap the target. The loop is the same.",
    "Thank you for your time. We built Agent SRE on Google ADK, Gemini, and the Arize Phoenix MCP server — the exact stack this hackathon was built for. The code is open source on GitHub. The demo is live on Cloud Run. And we look forward to the opportunity to bring Agent SRE to production.",
]


def main() -> None:
    doc = SimpleDocTemplate(
        "VIDEO_SCRIPT.pdf",
        pagesize=LETTER,
        rightMargin=0.9 * inch,
        leftMargin=0.9 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title="Agent SRE — Video Script",
        author="Agent SRE",
    )

    title_style = ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=HexColor("#0a0a0a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=HexColor("#6b7280"),
        spaceAfter=20,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=11.5,
        leading=17,
        textColor=HexColor("#111827"),
        spaceAfter=11,
        alignment=0,  # left
    )

    story = [
        Paragraph("Agent SRE — Video Script", title_style),
        Paragraph(
            "Approximately 3 minutes spoken at conversational pace · "
            "Google Cloud Rapid Agent Hackathon · Arize partner track",
            subtitle_style,
        ),
        HRFlowable(width="100%", thickness=0.5, color=HexColor("#d1d5db"), spaceBefore=0, spaceAfter=14),
    ]
    for p in SCRIPT_PARAGRAPHS:
        story.append(Paragraph(p, body_style))

    story.append(Spacer(1, 0.2 * inch))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=HexColor("#d1d5db"), spaceBefore=4, spaceAfter=8)
    )
    story.append(
        Paragraph(
            "Live demo: agent-sre-dashboard-qnre34navq-uc.a.run.app · "
            "Source: github.com/OJ-IRO/agent-sre",
            subtitle_style,
        )
    )

    doc.build(story)
    print("Wrote VIDEO_SCRIPT.pdf")


if __name__ == "__main__":
    main()
