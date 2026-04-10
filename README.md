# Multi-Agent Stock Analyzer

A multi-agent AI system built on [CrewAI](https://crewai.com) that conducts end-to-end equity research — from macroeconomic news collection and financial analysis to technical charting and a final Buy/Hold/Sell recommendation — delivered as a professional PDF report.

---

## End-to-End Workflow

```
User Input: { symbol: "TSLA", current_date: "2026-04-09" }
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1 — CrewAI Crew  (src/stock_advisor/main.py → crew.py)    │
│                                                                   │
│  ┌────────────────────┐  ┌───────────────────┐  ┌─────────────┐  │
│  │ News Researcher    │  │ Fundamental       │  │ Technical   │  │
│  │ (async)            │  │ Analyst (async)   │  │ Analyst     │  │
│  │                    │  │                   │  │ (async)     │  │
│  │ → us_market_       │  │ → fundamental_    │  │ → technical │  │
│  │   analysis.md      │  │   analysis.md     │  │  _analysis  │  │
│  └────────────────────┘  └───────────────────┘  │  .md        │  │
│                                                  │ + 3x .jpg   │  │
│                                                  └─────────────┘  │
│                            ▼ (all 3 as context)                   │
│                ┌───────────────────────────────┐                  │
│                │   Investment Strategist        │                  │
│                │   (sequential, no tools)       │                  │
│                │   → final_decision.json        │                  │
│                └───────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2 — content_gen.py  (manual trigger)                       │
│  Reads : 3x .md + final_decision.json + 3x .jpg                  │
│  Calls : Gemini 2.5 Flash (multimodal)                           │
│  Output: report.md                                               │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3 — pdf_generator.py  (manual trigger)                     │
│  Reads  : report.md                                              │
│  Converts: Markdown → HTML → PDF  (pdfkit / wkhtmltopdf)         │
│  Output : report_from_md.html  +  US_equity_report.pdf           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

| Agent | LLM | Execution | Tools | Output File |
|---|---|---|---|---|
| **Stock News Researcher** | `ollama/llama3.2:3b` | Async | SerperDevTool, FirecrawlScrapeWebsiteTool, WebsiteSearchTool | `us_market_analysis.md` |
| **Fundamental Analyst** | `ollama/llama3.2:3b` | Async | USFundDataTool, USSectorValuationTool | `fundamental_analysis.md` |
| **Technical Analyst** | `ollama/llama3.2:3b` | Async | USTechDataTool, StockPriceLineChartTool, RevenueBarChartTool, MarketShareAllPeersDonutTool | `technical_analysis.md` + 3x `.jpg` |
| **Investment Strategist** | `ollama/gemma3:4b` | Sequential (after all 3) | *(none — synthesis only)* | `final_decision.json` |

Tasks 1–3 run **in parallel (async)**. Task 4 receives all three outputs as context and runs **sequentially after all three complete**.

### Investment Decision Output Schema (`final_decision.json`)

```json
{
  "stock_ticker":    "string",
  "full_name":       "string",
  "industry":        "string",
  "today_date":      "YYYY-MM-DD",
  "current_price":   float,
  "target_price":    float,
  "expected_return": float,
  "decision":        "BUY | HOLD | SELL",
  "macro_reasoning": "string",
  "fund_reasoning":  "string",
  "tech_reasoning":  "string"
}
```

---

## Tools Reference

### Custom Tools — `src/stock_advisor/tools/custom_tool.py`

#### Data Tools

| Class | Tool Name | API / Library | Returns |
|---|---|---|---|
| `USFundDataTool` | "Fundamental data lookup (US market)" | **yfinance** | P/E, P/B, ROE, ROA, EPS, D/E, profit margin, EV/EBITDA + last-4-quarter Revenue / Gross Profit / Net Income |
| `USTechDataTool` | "Technical data lookup (US market)" | **yfinance** (500-day OHLC history) | SMA(20/50/200), EMA(12/26), RSI-14, MACD + Signal + Histogram, Bollinger Bands, 3 nearest support & resistance clusters, trend interpretation string |
| `USSectorValuationTool` | "US Sector Valuation Scraper" | **yfinance** — 22 sector ETFs (XLK, XLF, XLV …) | Writes `us_sector_valuation.json`; returns JSON string of sector P/E & P/B |

#### Chart Tools

| Class | Tool Name | API / Library | Returns |
|---|---|---|---|
| `StockPriceLineChartTool` | "Stock price line chart (US)" | **yfinance** + **matplotlib** | Saves `{TICKER}_price_line.jpg`, returns filename |
| `RevenueBarChartTool` | "Revenue bar chart (US)" | **yfinance** + **matplotlib** | Saves `{TICKER}_revenue_bar.jpg`, returns filename |
| `MarketShareAllPeersDonutTool` | "Market share donut chart (all peers)" | **Finnhub REST API** (peer list) + **yfinance** (market caps) + **matplotlib** | Saves `{TICKER}_market_share_all.jpg`, returns filename |

#### Report / Utility Tools (defined, currently unused in crew)

| Class | Tool Name | Library | Returns |
|---|---|---|---|
| `MarkdownRenderTool` | "Markdown → HTML" | **markdown** | HTML string |
| `WeasyPrintTool` | "HTML → PDF (WeasyPrint)" | **weasyprint** | PDF file path |
| `ImageToPdfTool` | "Image → PDF" | **weasyprint** | PDF file path |
| `PdfMergeTool` | "Merge PDFs" | **pypdf** | Merged PDF file path |
| `FileReadTool` | "Read a file's content" | built-in `open()` | File content string |

### Third-Party CrewAI Tools (instantiated in `crew.py`)

| Tool | External API | Key Config |
|---|---|---|
| `SerperDevTool` | **Serper.dev** — Google Search (`SERPER_API_KEY`) | country=us, locale=us, location=New York |
| `FirecrawlScrapeWebsiteTool` | **Firecrawl** — web scraper (`FIRECRAWL_API_KEY`) | timeout=60 |
| `WebsiteSearchTool` | Semantic search (local embeddings) | LLM=llama3.2:3b, embedder=nomic-embed-text (Ollama) |

### Post-Processing Scripts

| Script | External API | Role |
|---|---|---|
| `content_gen.py` | **Google Generative AI** — `gemini-2.5-flash-preview-04-17` (`GEMINI_API_KEY`) | Reads 3x `.md` + `final_decision.json` + 3x `.jpg` → assembles `report.md` via multimodal prompt |
| `pdf_generator.py` | **pdfkit** + `wkhtmltopdf` | Converts `report.md` → `report_from_md.html` → `US_equity_report.pdf` |

---

## File Outputs

All files currently land in the project root directory.

| File | Generated By | Description |
|---|---|---|
| `us_market_analysis.md` | News Researcher agent | 3-page macro/policy news summary with 5 key articles |
| `fundamental_analysis.md` | Fundamental Analyst agent | 3-page financial ratios, quarterly trends, industry comparison |
| `technical_analysis.md` | Technical Analyst agent | 3-page indicators report with trend interpretation |
| `final_decision.json` | Investment Strategist agent | Structured Buy/Hold/Sell recommendation with reasoning |
| `{TICKER}_price_line.jpg` | StockPriceLineChartTool | 6-month closing price line chart |
| `{TICKER}_revenue_bar.jpg` | RevenueBarChartTool | Last-4-period revenue bar chart (USD billions) |
| `{TICKER}_market_share_all.jpg` | MarketShareAllPeersDonutTool | Market-cap share donut vs. all Finnhub peers |
| `us_sector_valuation.json` | USSectorValuationTool | P/E & P/B for 22 US sectors (reference data) |
| `report.md` | content_gen.py (Gemini) | Assembled institutional-style research report |
| `report_from_md.html` | pdf_generator.py | HTML render of report.md |
| `US_equity_report.pdf` | pdf_generator.py | Final distributable PDF report |

---

## Refactoring Plan

### Problems in the Current Codebase

| # | Problem | Impact |
|---|---|---|
| 1 | All outputs scatter to the project root | Runs for different tickers overwrite each other |
| 2 | `custom_tool.py` is a 700-line monolith with 11 unrelated tool classes | Hard to test, extend, or import selectively |
| 3 | `crew.py` mixes LLM config, tool setup, agent definitions, task definitions, and the output Pydantic model | Single-responsibility violation; hard to maintain |
| 4 | `content_gen.py` and `pdf_generator.py` are standalone scripts | Not integrated into the crew, not importable, not testable |
| 5 | Tickers hardcoded in `main.py` (`TSLA`, `MSFT`, `AAPL`) | Must edit source to change the analysis target |
| 6 | `pdf_generator.py` hardcodes a Windows path to `wkhtmltopdf.exe` | Breaks on macOS/Linux |
| 7 | Dead commented-out code (publishing agent, render/merge tasks, PDF tools) | Noise; misleads contributors |
| 8 | Charting tasks defined in crew but excluded from `@crew` method | Charts never run as part of the pipeline |
| 9 | `MarketShareAllPeersDonutTool` reads `FINHUB_API_KEY` (typo) instead of `FINNHUB_API_KEY` | Tool silently fails every run |
| 10 | `.env` is tracked by git (contains real API keys) | Credential exposure in git history |

### Proposed Directory Structure

```
stock_advisor/
├── src/stock_advisor/
│   ├── __init__.py
│   ├── main.py                   # CLI: accepts --symbol argument
│   ├── crew.py                   # Only: agent/task wiring + @crew method
│   ├── llm_config.py             # NEW: LLM instantiation (local/Gemini toggle)
│   ├── models.py                 # NEW: InvestmentDecision Pydantic model
│   ├── pipeline.py               # NEW: content_gen + pdf_generator logic (importable)
│   ├── config/
│   │   ├── agents.yaml
│   │   └── tasks.yaml
│   └── tools/
│       ├── __init__.py           # Re-exports all tools
│       ├── data_tools.py         # NEW: USFundDataTool, USTechDataTool, USSectorValuationTool
│       ├── chart_tools.py        # NEW: StockPriceLineChartTool, RevenueBarChartTool, MarketShareAllPeersDonutTool
│       └── report_tools.py       # NEW: MarkdownRenderTool, WeasyPrintTool, ImageToPdfTool, PdfMergeTool, FileReadTool
├── output/                       # NEW: per-run isolated output directories
│   └── {TICKER}_{DATE}/
│       ├── us_market_analysis.md
│       ├── fundamental_analysis.md
│       ├── technical_analysis.md
│       ├── final_decision.json
│       ├── {TICKER}_price_line.jpg
│       ├── {TICKER}_revenue_bar.jpg
│       ├── {TICKER}_market_share_all.jpg
│       ├── report.md
│       └── US_equity_report.pdf
├── knowledge/
│   ├── PE_PB_industry_average_eng.json
│   └── PE_PB_industry_average_eng.txt
├── tests/
├── pyproject.toml
├── .env                          # add to .gitignore immediately
└── README.md
```

### Refactoring Steps

| # | Change | Benefit |
|---|---|---|
| 1 | Split `custom_tool.py` into `data_tools.py`, `chart_tools.py`, `report_tools.py` | Single responsibility; easier to test and import selectively |
| 2 | Extract LLM config to `llm_config.py` with a `use_local: bool` toggle | Switch between Ollama and Gemini without touching `crew.py` |
| 3 | Extract `InvestmentDecision` Pydantic model to `models.py` | Reusable across crew, pipeline, and tests |
| 4 | Create `pipeline.py` wrapping `content_gen` + `pdf_generator` logic | Phase 2 & 3 callable from `main.py` after crew finishes; fully testable |
| 5 | Route all file outputs to `output/{TICKER}_{DATE}/` | Isolates runs per ticker/date; no root-level clutter; easy to archive |
| 6 | Accept `--symbol` CLI argument in `main.py` | No more hardcoded tickers |
| 7 | Fix `FINHUB_API_KEY` → `FINNHUB_API_KEY` typo in `MarketShareAllPeersDonutTool` | Tool actually works |
| 8 | Integrate charting tasks into main crew flow before the technical analysis task | Charts exist on disk when the technical analyst writes its report |
| 9 | Remove all dead commented-out code | Cleaner, readable codebase |
| 10 | Add `.env` to `.gitignore` | Prevents API key leakage in git history |

---

## Installation

Requires Python `>=3.10, <3.13`. Uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
pip install uv
crewai install
```

Copy `.env.example` to `.env` and fill in your API keys:

```
GEMINI_API_KEY=...
SERPER_API_KEY=...
FIRECRAWL_API_KEY=...
FINNHUB_API_KEY=...
```

Ollama must be running locally with the following models pulled:

```bash
ollama pull llama3.2:3b
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

## Running

```bash
# Phase 1 — run the crew
crewai run

# Phase 2 — assemble the report
python content_gen.py

# Phase 3 — generate PDF
python pdf_generator.py
```
