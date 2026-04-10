from __future__ import annotations
import os
from pathlib import Path
from typing import Literal, Optional, Type

import matplotlib
import matplotlib.pyplot as plt
import requests
import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

matplotlib.use("Agg")


class USStockInput(BaseModel):
    """Input schema for US stock tools."""
    ticker: str = Field(..., description="U.S. stock ticker symbol (e.g. AAPL).")


class PriceChartInput(USStockInput):
    period: str = Field("6mo", description="Look-back window (1mo, 3mo, 6mo, 1y, etc.)")
    interval: str = Field("1d", description="Bar size (1d, 1wk, 1mo)")


class RevenueChartInput(USStockInput):
    freq: Literal["annual", "quarterly"] = Field(
        "annual", description="Use annual or quarterly statement"
    )


class MarketShareInput(USStockInput):
    api_key: Optional[str] = Field(None, description="Finnhub API key (overrides env var)")


# ---------------------------------------------------------------------------
# Stock Price Line Chart Tool
# ---------------------------------------------------------------------------

class StockPriceLineChartTool(BaseTool):
    name: str = "Stock price line chart (US)"
    description: str = (
        "Draws and saves a line chart of close-price history for a U.S. ticker. "
        "Returns the saved JPEG filename."
    )
    args_schema: Type[BaseModel] = PriceChartInput

    def _run(self, ticker: str, period: str = "6mo", interval: str = "1d") -> str:
        df = yf.download(ticker.upper(), period=period, interval=interval, progress=False)
        if df.empty:
            return f"❌ No data for {ticker}."

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df.index, df["Close"])
        ax.set(
            title=f"{ticker.upper()} close – last {period}",
            xlabel="Date",
            ylabel="Price (USD)",
        )
        outfile = f"{ticker.upper()}_price_line.jpg"
        plt.tight_layout()
        plt.savefig(outfile, dpi=300)
        plt.close(fig)
        return outfile


# ---------------------------------------------------------------------------
# Revenue Bar Chart Tool
# ---------------------------------------------------------------------------

class RevenueBarChartTool(BaseTool):
    name: str = "Revenue bar chart (US)"
    description: str = "Builds a bar chart of the last 4 revenues (annual/quarterly)."
    args_schema: Type[BaseModel] = RevenueChartInput

    def _run(self, ticker: str, freq: str = "annual") -> str:
        fin = yf.Ticker(ticker.upper())
        stmt = fin.financials if freq == "annual" else fin.quarterly_financials
        if stmt.empty:
            return f"❌ No {freq} income statement for {ticker}."

        key = "Total Revenue" if "Total Revenue" in stmt.index else "Revenue"
        revenue = stmt.loc[key].dropna().iloc[:4][::-1]

        fig, ax = plt.subplots(figsize=(8, 4))
        labels = (
            revenue.index.year.astype(str)
            if freq == "annual"
            else revenue.index.strftime("%Y-%m")
        )
        ax.bar(labels, revenue / 1e9)
        ax.set(
            title=f"{ticker.upper()} {freq.title()} Revenue",
            ylabel="USD (billions)",
        )
        outfile = f"{ticker.upper()}_revenue_bar.jpg"
        plt.tight_layout()
        plt.savefig(outfile, dpi=300)
        plt.close(fig)
        return outfile


# ---------------------------------------------------------------------------
# Market Share Donut Chart Tool
# ---------------------------------------------------------------------------

class MarketShareAllPeersDonutTool(BaseTool):
    name: str = "Market share donut chart (all peers)"
    description: str = (
        "Fetches the full peer list from Finnhub for a U.S. ticker, gets each "
        "company's market cap via Yahoo Finance, and draws a donut chart whose "
        "legend shows labels in the form 'SYM (xx.x %)'."
    )
    args_schema: Type[BaseModel] = MarketShareInput

    _PEER_URL: str = "https://finnhub.io/api/v1/stock/peers"

    def _run(self, ticker: str, api_key: Optional[str] = None) -> str:
        # Resolve API key — prefer argument, then environment variable
        resolved_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not resolved_key:
            return "❌ Finnhub API key not supplied (pass api_key or set FINNHUB_API_KEY in .env)."

        try:
            resp = requests.get(
                self._PEER_URL,
                params={"symbol": ticker.upper(), "token": resolved_key},
                timeout=8,
            )
            resp.raise_for_status()
            peers: list[str] = resp.json() or []
        except Exception as exc:
            return f"❌ Finnhub peers API error: {exc}"

        symbols = list({ticker.upper(), *peers})

        caps: dict[str, int] = {}
        for sym in symbols:
            try:
                cap = yf.Ticker(sym).info.get("marketCap")
                if cap:
                    caps[sym] = cap
            except Exception:
                continue

        if len(caps) < 2:
            return f"❌ Not enough market-cap data for {ticker} and peers."

        target_cap = caps.pop(ticker.upper(), None)
        if target_cap is None:
            target_cap, _ = caps.popitem()

        labels_syms = [ticker.upper(), *caps.keys()]
        sizes = [target_cap, *caps.values()]
        total = sum(sizes)
        legend_labels = [
            f"{sym} ({100 * val / total:.1f} %)" for sym, val in zip(labels_syms, sizes)
        ]

        fig, ax = plt.subplots(figsize=(7, 7))
        wedges, _ = ax.pie(
            sizes,
            wedgeprops=dict(width=0.35),
            startangle=90,
            labels=None,
        )
        ax.set(
            aspect="equal",
            title=f"{ticker.upper()} vs ALL peers\nMarket-cap share",
        )
        ax.legend(
            wedges,
            legend_labels,
            title="Market share",
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=8,
        )

        outfile = f"{ticker.upper()}_market_share_all.jpg"
        plt.tight_layout()
        plt.savefig(outfile, dpi=300)
        plt.close(fig)
        return outfile
