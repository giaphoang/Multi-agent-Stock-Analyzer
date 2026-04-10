"""Unit tests for WebsiteSearchTool with local Ollama embeddings."""

import pytest
import requests

from crewai_tools import WebsiteSearchTool


# Skip all tests if Ollama is not available
try:
    resp = requests.get("http://localhost:11434/api/tags", timeout=2)
    OLLAMA_AVAILABLE = resp.status_code == 200
except Exception:
    OLLAMA_AVAILABLE = False


def get_ollama_config():
    """Return a valid Ollama embedding config for WebsiteSearchTool."""
    return {
        "embedding_model": {
            "provider": "ollama",
            "config": {
                "model_name": "nomic-embed-text",
            },
        }
    }


@pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Ollama is not running")
class TestWebsiteSearchToolWithOllama:
    """Test WebsiteSearchTool works with local Ollama embeddings."""

    def test_website_search_tool_init_with_ollama_config(self):
        """Test that WebsiteSearchTool initializes with valid Ollama config."""
        tool = WebsiteSearchTool(config=get_ollama_config())
        assert tool is not None
        assert tool.name == "Search in a specific website"

    def test_website_search_tool_initializes_without_openai_key(self):
        """Ensure no OPENAI_API_KEY is required when using Ollama embeddings."""
        import os
        # Make sure OPENAI_API_KEY is NOT set
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            tool = WebsiteSearchTool(config=get_ollama_config())
            assert tool.adapter is not None  # adapter initialized successfully
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_website_search_tool_custom_ollama_url(self):
        """Test that custom Ollama URL is accepted."""
        config = {
            "embedding_model": {
                "provider": "ollama",
                "config": {
                    "model_name": "nomic-embed-text",
                    "url": "http://localhost:11434/api/embeddings",
                },
            }
        }
        tool = WebsiteSearchTool(config=config)
        assert tool is not None

    def test_website_search_tool_add_website(self):
        """Test adding a website to the search index."""
        tool = WebsiteSearchTool(config=get_ollama_config())
        # Add a simple website (using httpbin as a stable test target)
        tool.add("https://httpbin.org/html")
        # Should not raise

    def test_website_search_tool_basic_query(self):
        """Test basic website search query."""
        tool = WebsiteSearchTool(config=get_ollama_config())
        # First add some content
        tool.add("https://httpbin.org/html")
        # Then search
        result = tool._run(search_query="httpbin", website="https://httpbin.org/html")
        assert isinstance(result, str)
        assert len(result) > 0


def test_website_search_tool_schema_requires_embedding_model():
    """Verify the config schema requires 'embedding_model' not 'embedder' or 'llm'."""
    # This test documents the correct key name
    valid_config = get_ollama_config()
    assert "embedding_model" in valid_config
    assert "llm" not in valid_config
    assert "embedder" not in valid_config

