#!/usr/bin/env python
"""Test script to run individual agents and see which one fails."""

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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from crewai import Agent, Task, Crew, LLM


def test_ollama_connection():
    """Test if Ollama is running and models are available."""
    import requests
    
    print("\n" + "=" * 80)
    print("Testing Ollama Connection")
    print("=" * 80)
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        data = response.json()
        models = [model["name"] for model in data.get("models", [])]
        
        print(f"✅ Ollama is running!")
        print(f"Available models: {models}")
        
        required_models = ["gemma3:4b", "nomic-embed-text"]
        missing = [m for m in required_models if not any(m in model for model in models)]
        
        if missing:
            print(f"⚠️  Missing models: {missing}")
            print("Install them with:")
            for model in missing:
                print(f"  ollama pull {model}")
            return False
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Ollama is NOT running!")
        print("Start it with: ollama serve")
        return False
    except Exception as e:
        print(f"❌ Error connecting to Ollama: {e}")
        return False


def test_llm():
    """Test if LLM can be initialized."""
    print("\n" + "=" * 80)
    print("Testing LLM Initialization")
    print("=" * 80)
    
    try:
        llm = LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")
        print("✅ LLM initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize LLM: {e}")
        return False


def test_tools():
    """Test if tools can be initialized."""
    print("\n" + "=" * 80)
    print("Testing Tools Initialization")
    print("=" * 80)
    
    try:
        from stock_advisor.tools.custom_tool import (
            USFundDataTool,
            USTechDataTool,
            USSectorValuationTool,
        )
        
        fund_tool = USFundDataTool()
        print("✅ USFundDataTool initialized")
        
        tech_tool = USTechDataTool(result_as_answer=True)
        print("✅ USTechDataTool initialized")
        
        sector_tool = USSectorValuationTool()
        print("✅ USSectorValuationTool initialized")
        
        return True
    except Exception as e:
        print(f"❌ Failed to initialize tools: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_creation():
    """Test if an agent can be created."""
    print("\n" + "=" * 80)
    print("Testing Agent Creation")
    print("=" * 80)
    
    try:
        from stock_advisor.tools.custom_tool import (
            USFundDataTool,
            USSectorValuationTool,
        )
        
        llm = LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")
        fund_tool = USFundDataTool()
        sector_tool = USSectorValuationTool()
        
        agent = Agent(
            role="Test Agent",
            goal="Test agent creation",
            backstory="Testing agent initialization",
            verbose=True,
            llm=llm,
            tools=[fund_tool, sector_tool],
            embedder={
                "provider": "ollama",
                "config": {"model_name": "nomic-embed-text"},
            },
        )
        print("✅ Agent created successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_task():
    """Test if an agent can execute a simple task."""
    print("\n" + "=" * 80)
    print("Testing Agent Task Execution")
    print("=" * 80)
    
    try:
        from stock_advisor.tools.custom_tool import (
            USFundDataTool,
            USSectorValuationTool,
        )
        
        llm = LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")
        fund_tool = USFundDataTool()
        sector_tool = USSectorValuationTool()
        
        agent = Agent(
            role="Fundamental Analyst",
            goal="Analyze fundamental data",
            backstory="Expert in fundamental analysis",
            verbose=True,
            llm=llm,
            tools=[fund_tool, sector_tool],
        )
        
        task = Task(
            description="Get fundamental data for AAPL stock",
            expected_output="Financial metrics for AAPL",
            agent=agent,
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=True)
        
        print("Executing task (this may take a moment)...")
        result = crew.kickoff()
        
        print("✅ Task executed successfully!")
        print(f"Result:\n{result}")
        return True
    except Exception as e:
        print(f"❌ Task execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all diagnostic tests."""
    print("\n" + "=" * 80)
    print("AGENT DIAGNOSTIC TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Ollama Connection", test_ollama_connection),
        ("LLM Initialization", test_llm),
        ("Tools Initialization", test_tools),
        ("Agent Creation", test_agent_creation),
        ("Agent Task Execution", test_agent_task),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error in {test_name}: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
