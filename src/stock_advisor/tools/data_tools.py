from __future__ import annotations
from typing import Dict, Optional, Type
import json

import numpy as np
import pandas as pd
import yfinance as yf
from crewai.tools import BaseTool
from datetime import datetime, timedelta
from pydantic import BaseModel, Field


class USStockInput(BaseModel):
    """Input schema for US stock tools."""
    ticker: str = Field(..., description="U.S. stock ticker symbol (e.g. AAPL).")


class EmptyInput(BaseModel):
    """No input required."""
    pass


# ---------------------------------------------------------------------------
# Fundamental Data Tool
# ---------------------------------------------------------------------------

class USFundDataTool(BaseTool):
    """Fetch quarterly fundamentals & key ratios for U.S. equities via yfinance."""

    name: str = "Fundamental data lookup (US market)"
    description: str = (
        "Retrieve key valuation ratios (P/E, P/B, ROE, etc.) and last 4 "
        "quarterly income-statement trends for a given U.S. stock ticker using "
        "Yahoo Finance data."
    )
    args_schema: Type[BaseModel] = USStockInput

    def _run(self, ticker: str) -> str:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            full_name = info.get("longName", "N/A")
            sector = info.get("sector", "N/A")
            industry = info.get("industry", "N/A")

            pe_ratio = info.get("trailingPE", "N/A")
            pb_ratio = info.get("priceToBook", "N/A")
            roe = info.get("returnOnEquity", "N/A")
            roa = info.get("returnOnAssets", "N/A")
            eps = info.get("trailingEps", "N/A")
            de = info.get("debtToEquity", "N/A")
            profit_margin = info.get("profitMargins", "N/A")
            evebitda = info.get("enterpriseToEbitda", "N/A")

            try:
                income_stmt = stock.quarterly_financials
                revenue = income_stmt.loc["Total Revenue"].tolist()
                gross_profit = income_stmt.loc["Gross Profit"].tolist()
                net_income = income_stmt.loc["Net Income"].tolist()
                quarters = income_stmt.columns.tolist()
            except Exception:
                revenue = gross_profit = net_income = quarters = []

            quarterly_trends = []
            for i in range(min(4, len(quarters))):
                rev = f"${revenue[i]:,.0f}" if i < len(revenue) and revenue[i] else "N/A"
                gp = f"${gross_profit[i]:,.0f}" if i < len(gross_profit) and gross_profit[i] else "N/A"
                ni = f"${net_income[i]:,.0f}" if i < len(net_income) and net_income[i] else "N/A"
                quarterly_trends.append(
                    f"\nQuarter T-{i + 1} ({quarters[i].strftime('%Y-%m-%d')}):\n"
                    f"- Revenue: {rev}\n- Gross Profit: {gp}\n- Net Income: {ni}\n"
                )

            return (
                f"📊 Stock Symbol: {ticker}\n"
                f"Company Name: {full_name}\nSector: {sector}\nIndustry: {industry}\n"
                f"P/E Ratio: {pe_ratio}\nP/B Ratio: {pb_ratio}\nROE: {roe}\nROA: {roa}\n"
                f"Profit Margin: {profit_margin}\nEPS: {eps}\nD/E Ratio: {de}\n"
                f"EV/EBITDA: {evebitda}\n\n"
                f"📈 LATEST 4 QUARTERS TREND:\n{''.join(quarterly_trends)}"
            )
        except Exception as e:
            return f"Error retrieving fundamental data: {e}"


# ---------------------------------------------------------------------------
# Technical Data Tool
# ---------------------------------------------------------------------------

class USTechDataTool(BaseTool):
    """Compute common technical indicators for a U.S. equity using yfinance."""

    name: str = "Technical data lookup (US market)"
    description: str = (
        "Retrieve OHLC price history (200 trading days) via Yahoo Finance and "
        "compute SMA/EMA (20/50/200, 12/26), RSI-14, MACD, Bollinger Bands, and "
        "the three nearest support/resistance clusters."
    )
    args_schema: Type[BaseModel] = USStockInput

    def _run(self, ticker: str) -> str:
        try:
            end = datetime.now()
            start = end - timedelta(days=500)

            df = yf.download(
                ticker,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=True,
                progress=False,
            )

            if df.empty:
                return f"❌ No price history available for {ticker.upper()}."

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df.rename(columns=str.lower)

            tech = self._calc_indicators(df)
            s_r = self._support_resistance(df)

            current_price = df["close"].iloc[-1]
            recent_prices = df["close"].iloc[-5:-1]
            ind = tech.iloc[-1]
            interpretation = self._get_interpretation(ind, current_price)

            return (
                f"\n📈 Stock Symbol: {ticker.upper()}\n"
                f"Current Price: ${current_price:,.2f}\n\n"
                f"RECENT CLOSING PRICES:\n"
                f"- T-1: ${recent_prices.iloc[-1]:,.2f}\n"
                f"- T-2: ${recent_prices.iloc[-2]:,.2f}\n"
                f"- T-3: ${recent_prices.iloc[-3]:,.2f}\n"
                f"- T-4: ${recent_prices.iloc[-4]:,.2f}\n\n"
                f"TECHNICAL INDICATORS (latest):\n"
                f"- SMA (20):  ${ind['SMA_20']:,.2f}\n"
                f"- SMA (50):  ${ind['SMA_50']:,.2f}\n"
                f"- SMA (200): ${ind['SMA_200']:,.2f}\n"
                f"- EMA (12):  ${ind['EMA_12']:,.2f}\n"
                f"- EMA (26):  ${ind['EMA_26']:,.2f}\n"
                f"- RSI (14):  {ind['RSI_14']:.2f}\n"
                f"- MACD:       {ind['MACD']:.2f}\n"
                f"- MACD Signal:{ind['MACD_Signal']:.2f}\n"
                f"- MACD Hist.: {ind['MACD_Hist']:.2f}\n"
                f"- Bollinger Upper:  ${ind['BB_Upper']:,.2f}\n"
                f"- Bollinger Middle: ${ind['BB_Middle']:,.2f}\n"
                f"- Bollinger Lower:  ${ind['BB_Lower']:,.2f}\n\n"
                f"SUPPORT & RESISTANCE:\n{s_r}\n\n"
                f"TECHNICAL INTERPRETATION:\n{interpretation}\n"
            )
        except Exception as exc:
            return f"❌ Error fetching technical data: {exc}"

    @staticmethod
    def _calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        data["SMA_20"] = data["close"].rolling(20).mean()
        data["SMA_50"] = data["close"].rolling(50).mean()
        data["SMA_200"] = data["close"].rolling(200).mean()
        data["EMA_12"] = data["close"].ewm(span=12, adjust=False).mean()
        data["EMA_26"] = data["close"].ewm(span=26, adjust=False).mean()
        data["MACD"] = data["EMA_12"] - data["EMA_26"]
        data["MACD_Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
        data["MACD_Hist"] = data["MACD"] - data["MACD_Signal"]
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        rs = gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan)
        data["RSI_14"] = (100 - (100 / (1 + rs))).fillna(50)
        data["BB_Middle"] = data["close"].rolling(20).mean()
        std = data["close"].rolling(20).std()
        data["BB_Upper"] = data["BB_Middle"] + 2 * std
        data["BB_Lower"] = data["BB_Middle"] - 2 * std
        return data

    @staticmethod
    def _support_resistance(df: pd.DataFrame, window: int = 10, thresh: float = 0.03) -> str:
        data = df.copy()
        data["local_max"] = data["high"].rolling(window=window, center=True).apply(
            lambda x: x.iloc[len(x) // 2] == x.max()
        )
        data["local_min"] = data["low"].rolling(window=window, center=True).apply(
            lambda x: x.iloc[len(x) // 2] == x.min()
        )
        highs = data.loc[data["local_max"] == 1, "high"].tolist()
        lows = data.loc[data["local_min"] == 1, "low"].tolist()
        current = data["close"].iloc[-1]

        def cluster(levels):
            if not levels:
                return []
            levels = sorted(levels)
            clusters = [[levels[0]]]
            for lvl in levels[1:]:
                if abs((lvl - clusters[-1][-1]) / clusters[-1][-1]) < thresh:
                    clusters[-1].append(lvl)
                else:
                    clusters.append([lvl])
            return [np.mean(c) for c in clusters]

        resist = [r for r in sorted(cluster(highs)) if r > current][:3]
        supp = [s for s in sorted(cluster(lows), reverse=True) if s < current][:3]
        out = [f"- R{i}: ${lvl:,.2f}" for i, lvl in enumerate(resist, 1)]
        if not resist:
            out.append("- (no significant resistance found)")
        out += [f"- S{i}: ${lvl:,.2f}" for i, lvl in enumerate(supp, 1)]
        if not supp:
            out.append("- (no significant support found)")
        return "\n".join(out)

    @staticmethod
    def _get_interpretation(ind: pd.Series, current: float) -> str:
        out = []
        if current > ind["SMA_200"] and ind["SMA_50"] > ind["SMA_200"]:
            out.append("- Long-term trend: BULLISH")
        elif current < ind["SMA_200"] and ind["SMA_50"] < ind["SMA_200"]:
            out.append("- Long-term trend: BEARISH")
        else:
            out.append("- Long-term trend: NEUTRAL")

        if current > ind["SMA_20"] and ind["SMA_20"] > ind["SMA_50"]:
            out.append("- Short-term trend: BULLISH")
        elif current < ind["SMA_20"] and ind["SMA_20"] < ind["SMA_50"]:
            out.append("- Short-term trend: BEARISH")
        else:
            out.append("- Short-term trend: NEUTRAL")

        if ind["RSI_14"] > 70:
            out.append("- RSI: OVERBOUGHT (>70)")
        elif ind["RSI_14"] < 30:
            out.append("- RSI: OVERSOLD (<30)")
        else:
            out.append(f"- RSI: NEUTRAL ({ind['RSI_14']:.2f})")

        out.append("- MACD: BULLISH" if ind["MACD"] > ind["MACD_Signal"] else "- MACD: BEARISH")

        if current > ind["BB_Upper"]:
            out.append("- Bollinger: OVERBOUGHT (above upper band)")
        elif current < ind["BB_Lower"]:
            out.append("- Bollinger: OVERSOLD (below lower band)")
        else:
            pct = (current - ind["BB_Lower"]) / (ind["BB_Upper"] - ind["BB_Lower"])
            if pct > 0.8:
                out.append("- Bollinger: Near overbought zone")
            elif pct < 0.2:
                out.append("- Bollinger: Near oversold zone")
            else:
                out.append("- Bollinger: Neutral zone")

        return "\n".join(out)


# ---------------------------------------------------------------------------
# Sector Valuation Tool
# ---------------------------------------------------------------------------

class USSectorValuationTool(BaseTool):
    name: str = "US Sector Valuation Scraper"
    description: str = (
        "Fetches current average P/E and P/B ratios for US market sectors "
        "using ETF proxies via yfinance, and saves the result as JSON."
    )
    args_schema: Type[BaseModel] = EmptyInput

    _SECTOR_ETFS: Dict[str, str] = {
        "Technology": "XLK",
        "Financials": "XLF",
        "Health Care": "XLV",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communication Services": "XLC",
        "Banking": "KBE",
        "Semiconductors": "SOXX",
        "Biotechnology": "IBB",
        "Aerospace & Defense": "ITA",
        "Retail": "XRT",
        "Metals & Mining": "XME",
        "Oil & Gas Exploration": "XOP",
        "Clean Energy": "ICLN",
        "Agribusiness": "MOO",
        "Transportation": "IYT",
        "Infrastructure": "PAVE",
    }

    def _run(self, **kwargs) -> str:
        def safe_float(value) -> Optional[float]:
            try:
                return float(value) if value is not None else None
            except (ValueError, TypeError):
                return None

        result = {}
        for sector, symbol in self._SECTOR_ETFS.items():
            info = yf.Ticker(symbol).info
            result[sector] = {
                "P/E": safe_float(info.get("trailingPE")),
                "P/B": safe_float(info.get("priceToBook")),
            }

        json_output = json.dumps(result, indent=4)
        with open("us_sector_valuation.json", "w") as f:
            f.write(json_output)

        return f"✅ Sector valuation data saved to 'us_sector_valuation.json'\n{json_output}"
