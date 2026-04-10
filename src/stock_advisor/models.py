from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class InvestmentDecision(BaseModel):
    """Structured JSON output for the final investment decision."""

    stock_ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")
    full_name: str = Field(..., description="Company full name")
    industry: str = Field(..., description="Industry / sector")
    today_date: str = Field(..., description="Analysis date (YYYY-MM-DD)")
    current_price: float = Field(..., description="Current stock price in USD")
    target_price: float = Field(..., description="Target price in USD")
    expected_return: float = Field(..., description="Expected return in %")
    decision: Literal["BUY", "HOLD", "SELL"] = Field(..., description="Investment decision")
    macro_reasoning: str = Field(..., description="Macro & news-driven justification")
    fund_reasoning: str = Field(..., description="Fundamental analysis rationale")
    tech_reasoning: str = Field(..., description="Technical analysis rationale")
