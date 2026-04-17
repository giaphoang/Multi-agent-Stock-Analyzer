# AGENTS.md — Multi-Agent Stock Analyzer

## Project Overview

A multi-agent AI system built on [CrewAI](https://crewai.com) that conducts end-to-end equity research — from macroeconomic news collection and financial analysis to technical charting and a final Buy/Hold/Sell recommendation — delivered as a professional PDF report.

## Project Structure

```
Multi-agent stock analyzer/
├── src/stock_advisor/
│   ├── main.py              # CLI entry point
│   ├── crew.py              # CrewAI crew definition (agents + tasks)
│   ├── pipeline.py          # Phase 2 & 3: report generation + PDF
│   ├── llm_config.py        # LLM configuration (local/Gemini toggle)
│   ├── models.py            # Pydantic models (InvestmentDecision)
│   ├── config/
│   │   ├── agents.yaml      # Agent role/goal/backstory definitions
│   │   └── tasks.yaml       # Task descriptions and expected outputs
│   └── tools/
│       ├── data_tools.py    # USFundDataTool, USTechDataTool, USSectorValuationTool
│       ├── chart_tools.py  # StockPriceLineChartTool, RevenueBarChartTool, MarketShareAllPeersDonutTool
│       └── report_tools.py # MarkdownRenderTool, WeasyPrintTool, PdfMergeTool, FileReadTool
├── output/                  # Per-run output directories (e.g., output/TSLA_2026-04-10/)
├── knowledge/               # Reference data (industry P/E, P/B averages)
├── tests/                   # Test scripts
└── .env                     # API keys (not tracked in git)
```

## Running the Project

```bash
# Default ticker (TSLA)
crewai run

# Specific ticker
crewai run -- --symbol AAPL

# Or directly
python -m stock_advisor.main --symbol NVDA
```

## Architecture

### Phase 1 — CrewAI Crew
Four agents run in parallel (async), then Investment Strategist runs sequentially:

| Agent | LLM | Tools | Output |
|-------|-----|-------|--------|
| Stock News Researcher | `ollama/llama3.2:3b` | SerperDevTool, FirecrawlScrapeWebsiteTool, WebsiteSearchTool | `us_market_analysis.md` |
| Fundamental Analyst | `ollama/llama3.2:3b` | USFundDataTool, USSectorValuationTool | `fundamental_analysis.md` |
| Technical Analyst | `ollama/llama3.2:3b` | USTechDataTool, StockPriceLineChartTool, RevenueBarChartTool, MarketShareAllPeersDonutTool | `technical_analysis.md` + 3x `.jpg` |
| Investment Strategist | `ollama/gemma3:4b` | (none) | `final_decision.json` |

### Phase 2 — Report Generation
- Reads: 3x `.md` files + `final_decision.json` + 3x `.jpg` charts
- Calls: Local Ollama (llava for vision) or Gemini 2.5 Flash
- Output: `report.md`

### Phase 3 — PDF Generation
- Converts: `report.md` → HTML → PDF
- Uses: pdfkit + wkhtmltopdf
- Output: `report_from_md.html`, `US_equity_report.pdf`

## LLM Configuration

Set `USE_LOCAL=true` (default) in `.env` to use Ollama models:
- `llm_general`: `ollama/llama3.2:3b`
- `llm_reasoning`: `ollama/gemma3:4b`
- `llm_vision`: `ollama/llava`

Set `USE_LOCAL=false` to use Gemini cloud:
- `llm_general`: `gemini/gemini-2.0-flash-001`
- `llm_reasoning`: `gemini/gemini-2.5-flash-preview-04-17`
- Requires: `GEMINI_API_KEY`

## Output Directory

All outputs go to `output/{TICKER}_{DATE}/` relative to project root:
- `output/TSLA_2026-04-10/us_market_analysis.md`
- `output/TSLA_2026-04-10/fundamental_analysis.md`
- `output/TSLA_2026-04-10/technical_analysis.md`
- `output/TSLA_2026-04-10/final_decision.json`
- `output/TSLA_2026-04-10/{TICKER}_price_line.jpg`
- `output/TSLA_2026-04-10/{TICKER}_revenue_bar.jpg`
- `output/TSLA_2026-04-10/{TICKER}_market_share_all.jpg`
- `output/TSLA_2026-04-10/report.md`
- `output/TSLA_2026-04-10/report_from_md.html`
- `output/TSLA_2026-04-10/US_equity_report.pdf`

## Key Files to Know

- `src/stock_advisor/main.py:40` — `run()` function, entry point
- `src/stock_advisor/crew.py:162` — `@crew` method, crew assembly
- `src/stock_advisor/pipeline.py:28` — `run_pipeline(ticker, date)`, Phase 2 & 3
- `src/stock_advisor/llm_config.py:8` — LLM model definitions
- `src/stock_advisor/models.py:6` — `InvestmentDecision` Pydantic model

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `USE_LOCAL` | No | `true` (default) for Ollama, `false` for Gemini |
| `GEMINI_API_KEY` | If USE_LOCAL=false | Google AI API key |
| `SERPER_API_KEY` | Yes | Serper.dev for web search |
| `FIRECRAWL_API_KEY` | Yes | Firecrawl for web scraping |
| `FINNHUB_API_KEY` | Yes | Finnhub for peer/market data |
| `WKHTMLTOPDF_PATH` | No | Path to wkhtmltopdf binary |

## Common Tasks

### Add a new agent
1. Add agent config in `config/agents.yaml`
2. Add task config in `config/tasks.yaml`
3. Add agent method in `crew.py`
4. Add task method in `crew.py`

### Add a new tool
1. Create tool class in appropriate file under `tools/`
2. Export in `tools/__init__.py`
3. Import and instantiate in `crew.py`

### Switch LLM provider
Edit `.env`: `USE_LOCAL=false` for Gemini, `USE_LOCAL=true` (default) for Ollama.

## Issue Workflow

When fixing a tracked GitHub issue, follow this closeout flow in the same session:

1. Implement the fix in code.
2. Run the smallest meaningful verification (targeted run/test).
3. Commit only the files related to that fix with an issue-referencing message.
4. Push the commit to `origin`.
5. Update or close the related GitHub issue when verification confirms the fix.

## Verified Runtime Workflow

Current stable run path:

1. Activate venv: `source .venv/bin/activate`
2. Run pipeline: `crewai run`
3. Verify outputs under `output/{TICKER}_{DATE}/`

Notes:
- News agent currently uses Serper-only tooling for stability.
- PDF output requires either:
  - `wkhtmltopdf` available in PATH (or `WKHTMLTOPDF_PATH`), or
  - WeasyPrint native deps installed (notably Pango/Cairo stack on macOS/Linux).
