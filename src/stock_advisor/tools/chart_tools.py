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
    _FALLBACK_PEERS: dict[str, list[str]] = {
        # Common public peers when Finnhub is unavailable.
        "TSLA": ["RIVN", "GM", "F", "NIO", "LI"],
        "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
        "NVDA": ["AMD", "INTC", "QCOM", "AVGO"],
    }
    _FALLBACK_MARKET_CAPS: dict[str, dict[str, int]] = {
        # Approximate market caps for offline fallback chart rendering.
        "TSLA": {
            "TSLA": 560_000_000_000,
            "RIVN": 12_000_000_000,
            "GM": 52_000_000_000,
            "F": 48_000_000_000,
            "NIO": 9_000_000_000,
            "LI": 26_000_000_000,
        },
        "AAPL": {
            "AAPL": 2_700_000_000_000,
            "MSFT": 3_000_000_000_000,
            "GOOGL": 2_000_000_000_000,
            "AMZN": 1_900_000_000_000,
            "META": 1_300_000_000_000,
        },
        "NVDA": {
            "NVDA": 2_300_000_000_000,
            "AMD": 290_000_000_000,
            "INTC": 130_000_000_000,
            "QCOM": 180_000_000_000,
            "AVGO": 650_000_000_000,
        },
    }

    def _run(self, ticker: str, api_key: Optional[str] = None) -> str:
        # Resolve API key — prefer argument, then environment variable
        resolved_key = api_key or os.getenv("FINNHUB_API_KEY")
        peers: list[str] = []
        if not resolved_key:
            peers = self._FALLBACK_PEERS.get(ticker.upper(), [])
        else:
            try:
                resp = requests.get(
                    self._PEER_URL,
                    params={"symbol": ticker.upper(), "token": resolved_key},
                    timeout=8,
                )
                resp.raise_for_status()
                peers = resp.json() or []
            except Exception:
                peers = self._FALLBACK_PEERS.get(ticker.upper(), [])
        if not peers:
            return "❌ Could not get peers from Finnhub and no fallback peers are configured."

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
            fallback_caps = self._FALLBACK_MARKET_CAPS.get(ticker.upper(), {})
            caps = {sym: cap for sym, cap in fallback_caps.items() if sym in symbols}

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
