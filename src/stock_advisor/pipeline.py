"""
pipeline.py — Phase 2 & 3 post-processing pipeline.

Reads the crew's output files from an output directory, calls LLM to
assemble report.md, then converts it to HTML and PDF.

Usage (called automatically by main.py after the crew finishes):
    from stock_advisor.pipeline import run_pipeline
    run_pipeline(ticker="TSLA", date="2026-04-10")
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_CHART_FILENAMES = (
    "{ticker}_price_line.jpg",
    "{ticker}_revenue_bar.jpg",
    "{ticker}_market_share_all.jpg",
)




def run_pipeline(ticker: str, date: str, output_dir: Path | str) -> None:
    """
    Run Phase 2 (content_gen) and Phase 3 (pdf_generator) for the given ticker/date.

    Args:
        ticker: Stock ticker symbol (e.g., "TSLA")
        date: Date string in YYYY-MM-DD format (e.g., "2026-04-10")
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _ensure_required_charts(output_dir=output_dir, ticker=ticker)

    _generate_report_md(output_dir)
    _generate_pdf(output_dir)


# ---------------------------------------------------------------------------
# Phase 2 — Assemble report.md via LLM (multimodal)
# ---------------------------------------------------------------------------

def _generate_report_md(output_dir: Path) -> None:
    try:
        from PIL import Image
    except ImportError as e:
        print(f"[pipeline] Skipping report.md generation — missing dependency: {e}")
        return

    # Use local model config (supports both local Ollama and Gemini fallback)
    from stock_advisor.llm_config import llm_vision
    use_local = os.getenv("USE_LOCAL", "true").lower() != "false"

    # Read analysis files
    macro_md = (output_dir / "us_market_analysis.md").read_text(encoding="utf-8")
    fund_md = (output_dir / "fundamental_analysis.md").read_text(encoding="utf-8")
    tech_md = (output_dir / "technical_analysis.md").read_text(encoding="utf-8")
    decision = json.loads((output_dir / "final_decision.json").read_text(encoding="utf-8"))

    ticker = decision["stock_ticker"]
    company = decision["full_name"]
    date = decision["today_date"]
    rec = decision["decision"]
    target = decision["target_price"]
    exp_ret = decision["expected_return"]
    current = decision["current_price"]

    # Load charts if present
    chart_names = [pattern.format(ticker=ticker) for pattern in _CHART_FILENAMES]
    images = []
    for name in chart_names:
        p = output_dir / name
        if p.exists():
            images.append(Image.open(p))

    final_rec_block = (
        f"\n### Final Investment Recommendation\n\n"
        f"We assign a **{rec}** rating for **{company} ({ticker})** as of {date}.  \n"
        f"Our target price is **${target:.2f}**, implying an expected return of "
        f"**{exp_ret:.1f}%** from the current price of ${current:.2f}.\n"
    )

    system_prompt = f"""
You are the **Final-Assembly Editor** for our CrewAI pipeline.

We have three analyst Markdown files:
1. `us_market_analysis.md` — macroeconomic and policy news
2. `fundamental_analysis.md` — financial ratios, industry comparisons, and qualitative assessments
3. `technical_analysis.md` — market trend data, price momentum, and signals

We also have three charts (to be included in the Fundamental section):
- `{ticker}_price_line.jpg` — 6-month stock price trend
- `{ticker}_revenue_bar.jpg` — annual revenue trend (last 4 years)
- `{ticker}_market_share_all.jpg` — market share vs. competitors

Your task: synthesize all input into a structured Markdown report for **{company} ({ticker})** dated **{date}**.

─────────────────────────── FORMAT ─────────────────────────────

# U.S. Equity Research Report
## {ticker} — {date}

### Executive Summary
~150 words summary combining macro context, valuation, and technical outlook.

### Macroeconomic & Policy Outlook
A ~500–600 word professional summary based solely on `us_market_analysis.md`.
Must reflect tone of institutional research.

### Technical Analysis
Present all key indicators from `technical_analysis.md` in a clean table.
Use professional style with 300–400 word commentary on momentum, trend, and support/resistance levels.
Do **not** include any images here.

### Fundamental & Valuation Analysis
Insert full content from `fundamental_analysis.md`.
Then embed all three charts, each followed by a 200–300 word paragraph describing:
- Trends
- Fluctuations
- Implications for valuation
- Competitive context

Also include:
- DCF valuation model with assumptions (WACC, growth)
- P/E and EV/EBITDA comps
- SWOT or Porter's Five Forces summary
- 3-year forecasts for revenue, net income, EPS, and FCF
- Final rating: **Buy / Hold / Sell**, target price, expected return %
- Conclude with the CrewAI final recommendation from final_decision.json

### Risks & Catalysts
- *Three downside risks* (macro, execution, regulatory)
- *Two upside catalysts* (include timing & mechanisms)
Each bullet ≤50 words. Start with `-`, **bold** triggers, *italicize* affected metrics.

─────────────────────────── STYLE ───────────────────────────────
- Use **bold** sparingly — headings, ratings, key financial ratios
- Tables must be professional: headers bold, numbers right-aligned
- Image captions should be exact filenames
- Output must be pure **Markdown** — no HTML, PDF, or JSON tags
"""

    # Build prompt based on local vs cloud
    if use_local:
        # Local Ollama: use llava for vision via direct API call
        _generate_report_local(output_dir, system_prompt, macro_md, fund_md, tech_md, final_rec_block, images)
    else:
        # Gemini cloud: use the existing Google Generative AI approach
        _generate_report_gemini(output_dir, system_prompt, macro_md, fund_md, tech_md, final_rec_block, images)


def _generate_report_local(output_dir: Path, system_prompt: str, macro_md: str, fund_md: str, tech_md: str, final_rec_block: str, images) -> None:
    """Generate report.md using local Ollama with vision support."""
    try:
        import requests
    except ImportError as e:
        print(f"[pipeline] Skipping local generation — missing dependency: {e}")
        return

    # For local models, we need to send images as base64
    import base64
    from io import BytesIO

    image_parts = []
    for img in images:
        buf = BytesIO()
        img.save(buf, format='JPEG')
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        image_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": img_b64
            }
        })

    content = [
        {"type": "text", "text": system_prompt},
        *image_parts,
        {"type": "text", "text": f"\n### MACRO\n{macro_md}\n\n### FUNDAMENTAL\n{fund_md}\n{final_rec_block}\n\n### TECHNICAL\n{tech_md}\n"}
    ]

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llava",
                "prompt": f"{system_prompt}\n\n### MACRO\n{macro_md}\n\n### FUNDAMENTAL\n{fund_md}\n{final_rec_block}\n\n### TECHNICAL\n{tech_md}\n",
                "images": [img_parts["source"]["data"] for img_parts in image_parts] if image_parts else [],
                "stream": False
            },
            timeout=300
        )
        response.raise_for_status()
        result = response.json()
        final_md = result.get("response", "").strip()
    except Exception as e:
        print(f"[pipeline] Local LLM call failed: {e}")
        # Fallback to text-only without images
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": f"{system_prompt}\n\n### MACRO\n{macro_md}\n\n### FUNDAMENTAL\n{fund_md}\n{final_rec_block}\n\n### TECHNICAL\n{tech_md}\n",
                    "stream": False
                },
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            final_md = result.get("response", "").strip()
            print("[pipeline] Using text-only fallback (no image analysis)")
        except Exception as e2:
            print(f"[pipeline] Fallback also failed: {e2}")
            return

    if final_md.startswith("```markdown"):
        final_md = final_md.removeprefix("```markdown").removesuffix("```").strip()

    out_path = output_dir / "report.md"
    out_path.write_text(final_md, encoding="utf-8")
    print(f"[pipeline] report.md written to {out_path}")


def _generate_report_gemini(output_dir: Path, system_prompt: str, macro_md: str, fund_md: str, tech_md: str, final_rec_block: str, images) -> None:
    """Generate report.md using Gemini cloud (existing implementation)."""
    try:
        import google.generativeai as genai
    except ImportError as e:
        print(f"[pipeline] Skipping Gemini generation — missing dependency: {e}")
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[pipeline] GEMINI_API_KEY not set — skipping report.md generation.")
        return

    prompt_parts = [
        system_prompt,
        *images,
        f"\n### MACRO\n{macro_md}\n\n### FUNDAMENTAL\n{fund_md}\n{final_rec_block}\n\n### TECHNICAL\n{tech_md}\n",
    ]

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_REASONING_MODEL", "gemini-2.5-flash-preview-04-17")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt_parts, stream=False)
    final_md = response.text.strip()
    if final_md.startswith("```markdown"):
        final_md = final_md.removeprefix("```markdown").removesuffix("```").strip()

    out_path = output_dir / "report.md"
    out_path.write_text(final_md, encoding="utf-8")
    print(f"[pipeline] report.md written to {out_path}")


# ---------------------------------------------------------------------------
# Phase 3 — Convert report.md → HTML → PDF
# ---------------------------------------------------------------------------

def _generate_pdf(output_dir: Path) -> None:
    try:
        import markdown as md_lib
    except ImportError:
        print("[pipeline] Skipping PDF generation — 'markdown' package not installed.")
        return

    report_md = output_dir / "report.md"
    if not report_md.exists():
        print(f"[pipeline] {report_md} not found — skipping PDF generation.")
        return

    markdown_text = report_md.read_text(encoding="utf-8")
    html_body = md_lib.markdown(
        markdown_text,
        extensions=["fenced_code", "tables", "toc", "md_in_html"],
    )

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Equity Research Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 40px;
            color: #333;
            font-size: 18px;
            line-height: 1.8;
        }}
        h1 {{ text-align: center; font-size: 40px; margin-bottom: 30px; }}
        h2 {{
            font-size: 28px; color: #2c3e50;
            border-bottom: 2px solid #ccc;
            padding-bottom: 8px; margin-top: 50px;
        }}
        h3 {{ font-size: 22px; color: #34495e; margin-top: 30px; }}
        p, li {{ font-size: 18px; }}
        table {{
            width: 100%; border-collapse: collapse; margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ccc; padding: 10px 14px;
            text-align: left; font-size: 16px;
        }}
        th {{ background-color: #f5f5f5; font-weight: bold; }}
        img {{ max-width: 100%; height: auto; display: block; margin: 30px auto; }}
        code {{
            background-color: #f4f4f4; padding: 2px 4px;
            font-size: 15px; font-family: Consolas, monospace;
        }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""

    html_path = output_dir / "report_from_md.html"
    html_path.write_text(full_html, encoding="utf-8")
    print(f"[pipeline] HTML written to {html_path}")

    pdf_path = output_dir / "US_equity_report.pdf"
    _html_to_pdf(html_path, pdf_path)


def _ensure_required_charts(output_dir: Path, ticker: str) -> None:
    """Generate missing chart artifacts inside the output directory."""
    missing = [
        name
        for name in (pattern.format(ticker=ticker) for pattern in _CHART_FILENAMES)
        if not (output_dir / name).exists()
    ]
    if not missing:
        return

    try:
        from stock_advisor.tools.chart_tools import (
            MarketShareAllPeersDonutTool,
            RevenueBarChartTool,
            StockPriceLineChartTool,
        )
    except Exception as exc:
        print(f"[pipeline] Could not load chart tools to generate missing charts: {exc}")
        return

    cwd = Path.cwd()
    try:
        os.chdir(output_dir)
        if f"{ticker}_price_line.jpg" in missing:
            StockPriceLineChartTool()._run(ticker=ticker)
        if f"{ticker}_revenue_bar.jpg" in missing:
            RevenueBarChartTool()._run(ticker=ticker)
        if f"{ticker}_market_share_all.jpg" in missing:
            MarketShareAllPeersDonutTool()._run(ticker=ticker)
    except Exception as exc:
        print(f"[pipeline] Failed generating one or more charts for {ticker}: {exc}")
    finally:
        os.chdir(cwd)

    still_missing = [name for name in missing if not (output_dir / name).exists()]
    if still_missing:
        print(f"[pipeline] Missing chart artifacts after generation: {', '.join(still_missing)}")


def _html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Convert HTML to PDF using pdfkit (cross-platform wkhtmltopdf detection)."""
    try:
        import pdfkit
    except ImportError:
        print("[pipeline] pdfkit not installed — skipping PDF conversion.")
        return

    wkhtmltopdf = _find_wkhtmltopdf()
    if wkhtmltopdf is None:
        if _html_to_pdf_weasyprint(html_path, pdf_path):
            return
        print("[pipeline] wkhtmltopdf not found and WeasyPrint fallback unavailable — skipping PDF conversion.")
        return

    config = pdfkit.configuration(wkhtmltopdf=str(wkhtmltopdf))
    options = {
        "enable-local-file-access": "",
        "page-size": "Letter",
        "margin-top": "0.75in",
        "margin-right": "0.75in",
        "margin-bottom": "0.75in",
        "margin-left": "0.75in",
        "encoding": "UTF-8",
    }
    pdfkit.from_file(str(html_path), str(pdf_path), configuration=config, options=options)
    print(f"[pipeline] PDF written to {pdf_path}")


def _html_to_pdf_weasyprint(html_path: Path, pdf_path: Path) -> bool:
    """Fallback converter when wkhtmltopdf is not available."""
    try:
        from weasyprint import HTML
    except Exception as exc:
        print(f"[pipeline] WeasyPrint import failed: {exc}")
        return False

    try:
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        print(f"[pipeline] PDF written to {pdf_path} (WeasyPrint fallback)")
        return True
    except Exception as exc:
        print(f"[pipeline] WeasyPrint PDF conversion failed: {exc}")
        return False


def _find_wkhtmltopdf() -> Optional[Path]:
    """Locate wkhtmltopdf cross-platform."""
    # 1. Environment variable override
    env_path = os.getenv("WKHTMLTOPDF_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    # 2. Common macOS / Linux locations (which)
    found = shutil.which("wkhtmltopdf")
    if found:
        return Path(found)

    # 3. Common Windows location
    win_path = Path("C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe")
    if win_path.is_file():
        return win_path

    return None
