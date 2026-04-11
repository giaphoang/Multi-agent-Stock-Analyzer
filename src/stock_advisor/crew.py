from __future__ import annotations
import os
import warnings
from pathlib import Path
from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FirecrawlScrapeWebsiteTool, SerperDevTool, WebsiteSearchTool, FileWriterTool
from dotenv import load_dotenv

from .llm_config import llm_general, llm_reasoning
from .models import InvestmentDecision
from .tools import (
    USFundDataTool,
    USSectorValuationTool,
    USTechDataTool,
    StockPriceLineChartTool,
    RevenueBarChartTool,
    MarketShareAllPeersDonutTool,
)

warnings.filterwarnings("ignore", category=UserWarning)

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=False)

# ---------------------------------------------------------------------------
# Tool instances
# ---------------------------------------------------------------------------

_fund_tool = USFundDataTool()
_tech_tool = USTechDataTool(result_as_answer=True)
_sector_tool = USSectorValuationTool()
_price_chart_tool = StockPriceLineChartTool()
_revenue_chart_tool = RevenueBarChartTool()
_market_share_tool = MarketShareAllPeersDonutTool()

_scrape_tool = FirecrawlScrapeWebsiteTool(
    timeout=60, api_key=os.getenv("FIRECRAWL_API_KEY")
)
_search_tool = SerperDevTool(
    country="us",
    locale="us",
    location="New York, New York, United States",
)
_web_search_tool = WebsiteSearchTool(
    config={
        "embedding_model": {
            "provider": "ollama",
            "config": {"model_name": "nomic-embed-text"},
        }
    }
)

_file_writer_tool = FileWriterTool()


def _write_session_log(content: str) -> None:
    """Write the latest session log to log.txt."""
    _file_writer_tool._run(filename="log.txt", content=content)


# ---------------------------------------------------------------------------
# Crew
# ---------------------------------------------------------------------------

@CrewBase
class USStockAdvisor:
    """CrewAI crew for analysing U.S. equities."""

    agents: List[BaseAgent]
    tasks: List[Task]

    # ── Agents ───────────────────────────────────────────────────────────────

    @agent
    def stock_news_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["stock_news_researcher"],
            verbose=True,
            llm=llm_general,
            tools=[_search_tool, _scrape_tool, _web_search_tool],
            max_rpm=10,
        )

    @agent
    def fundamental_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["fundamental_analyst"],
            verbose=True,
            llm=llm_general,
            tools=[_fund_tool, _sector_tool],
            max_rpm=10,
            embedder={
                "provider": "ollama",
                "config": {
                    "model": "nomic-embed-text:latest",
                    "base_url": "http://localhost:11434",
                },
            },
        )

    @agent
    def technical_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["technical_analyst"],
            verbose=True,
            llm=llm_general,
            tools=[_tech_tool, _revenue_chart_tool, _price_chart_tool, _market_share_tool],
            max_rpm=10,
        )

    @agent
    def investment_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["investment_strategist"],
            verbose=True,
            llm=llm_reasoning,
            max_rpm=10,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def news_collecting(self) -> Task:
        return Task(
            config=self.tasks_config["news_collecting"],
            agent=self.stock_news_researcher(),
            async_execution=True,
            output_file=str(self._output_dir_path / "us_market_analysis.md"),
        )

    @task
    def fundamental_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["fundamental_analysis"],
            agent=self.fundamental_analyst(),
            async_execution=True,
            output_file=str(self._output_dir_path / "fundamental_analysis.md"),
        )

    @task
    def technical_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["technical_analysis"],
            agent=self.technical_analyst(),
            async_execution=True,
            output_file=str(self._output_dir_path / "technical_analysis.md"),
        )

    @task
    def investment_decision(self) -> Task:
        return Task(
            config=self.tasks_config["investment_decision"],
            agent=self.investment_strategist(),
            context=[
                self.news_collecting(),
                self.fundamental_analysis(),
                self.technical_analysis(),
            ],
            output_json=InvestmentDecision,
            output_file=str(self._output_dir_path / "final_decision.json"),
        )

    # ── Crew ─────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    # ── Output directory ─────────────────────────────────────────────────────
    # Class-level default keeps CrewBase's getattr introspection safe.
    # Call set_output_dir() in main.py to route outputs to a per-run folder.
    _output_dir_path: Path = Path(__file__).parent.parent.parent / "output" / "default"

    def set_output_dir(self, path: Path) -> "USStockAdvisor":
        path.mkdir(parents=True, exist_ok=True)
        self._output_dir_path = path
        return self
