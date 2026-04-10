#!/usr/bin/env python
"""Test script to run the fundamental_analyst agent in isolation."""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Setup logging to see detailed execution
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from crewai import Agent, Task, Crew, LLM
from stock_advisor.tools.custom_tool import (
    USFundDataTool,
    USSectorValuationTool
)


def test_fundamental_agent():
    """Test the fundamental analyst agent."""
    
    # Initialize LLM
    llm_local = LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")
    
    # Initialize tools
    fund_tool = USFundDataTool()
    sector_valuation_tool = USSectorValuationTool()
    
    print("=" * 80)
    print("Testing Fundamental Analyst Agent")
    print("=" * 80)
    
    # Create agent
    agent = Agent(
        role="Fundamental Analysis Expert",
        goal="Analyze fundamental data for stocks",
        backstory="Expert in fundamental analysis and valuation metrics",
        verbose=True,
        llm=llm_local,
        tools=[fund_tool, sector_valuation_tool],
        max_rpm=10,
        embedder={
            "provider": "ollama",
            "config": {"model_name": "nomic-embed-text"},
        },
    )
    
    # Create a simple task
    task = Task(
        description="Analyze the fundamental data for Apple (AAPL) stock. Get financial metrics and industry valuation.",
        expected_output="A comprehensive analysis of AAPL fundamentals and how it compares to industry averages",
        agent=agent,
    )
    
    # Create and run crew
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )
    
    print("\n" + "=" * 80)
    print("Starting Agent Execution...")
    print("=" * 80 + "\n")
    
    try:
        result = crew.kickoff()
        print("\n" + "=" * 80)
        print("✅ Agent execution successful!")
        print("=" * 80)
        print("\nResult:")
        print(result)
        return True
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ Agent execution failed!")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_fundamental_agent()
    sys.exit(0 if success else 1)
