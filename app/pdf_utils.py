from fpdf import FPDF


def extract_summary_only(report_text: str) -> str:
    """Return executive summary if present; otherwise first 800 chars."""
    if not report_text:
        return "Summary unavailable."
    lower = report_text.lower()
    marker = "executive summary"
    if marker in lower:
        start_idx = lower.find(marker)
        return report_text[start_idx:].strip()
    return report_text[:800].strip() + ("..." if len(report_text) > 800 else "")


def build_summary_pdf(summary_text: str, title: str = "Video Report Summary") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    for line in summary_text.splitlines():
        pdf.multi_cell(0, 8, line)
    return pdf.output(dest="S").encode("latin-1")


