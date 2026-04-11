#!/usr/bin/env python
"""
main.py — CLI entry point for the Multi-Agent Stock Advisor.

Usage:
    crewai run                        # uses default ticker TSLA
    crewai run -- --symbol AAPL       # analyse a specific ticker
    python -m stock_advisor.main --symbol NVDA
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import date
from pathlib import Path

# Allow running as a script from the src/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from stock_advisor.crew import USStockAdvisor, _write_session_log
from stock_advisor.pipeline import run_pipeline

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


_OUTPUT_ROOT = "output"


def _parse_symbol() -> str:
    """Parse --symbol from argv; fall back to 'TSLA'."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--symbol", default="TSLA")
    args, _ = parser.parse_known_args()
    return args.symbol.upper()


def run() -> None:
    """Run the full pipeline for a given ticker symbol."""
    symbol = _parse_symbol()
    today = str(date.today())
    output_dir =  f"{_OUTPUT_ROOT}/{symbol}_{today}"

    print(f"[main] Analysing {symbol}  |  date={today}  |  output={output_dir}")

    inputs = {"symbol": symbol, "current_date": today}

    try:
        crew_result = USStockAdvisor().set_output_dir(output_dir).crew().kickoff(inputs=inputs)
        # Write session log
        _write_session_log(str(crew_result))
    except Exception as e:
        raise RuntimeError(f"Crew execution failed: {e}") from e

    # Phase 2 & 3 — assemble report.md and generate PDF
    run_pipeline(ticker=symbol, date=today, output_dir=output_dir)
    print(f"[main] Done. Outputs in {output_dir}")


def train() -> None:
    symbol = _parse_symbol()
    inputs = {"symbol": symbol, "current_date": str(date.today())}
    try:
        USStockAdvisor().crew().train(
            n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs
        )
    except Exception as e:
        raise RuntimeError(f"Train failed: {e}") from e


def replay() -> None:
    try:
        USStockAdvisor().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise RuntimeError(f"Replay failed: {e}") from e


def test() -> None:
    symbol = _parse_symbol()
    inputs = {"symbol": symbol, "current_date": str(date.today())}
    try:
        USStockAdvisor().crew().test(
            n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs
        )
    except Exception as e:
        raise RuntimeError(f"Test failed: {e}") from e
