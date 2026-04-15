import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from ollama_catalog.model_scraper import ModelScraper

def test_detect_url():
    scraper = ModelScraper()
    assert scraper.detect_url("llama2") == "https://ollama.com/library/llama2"
    assert scraper.detect_url("huihui_ai/qwen") == "https://ollama.com/huihui_ai/qwen"

def test_parse_pulls():
    scraper = ModelScraper()

    # Test plain pulls
    html = "<span>123</span> Pulls"
    assert scraper._parse_pulls(html) == (123, "123")

    # Test K
    html = "<span>1.2K</span> Pulls"
    assert scraper._parse_pulls(html) == (1200, "1.2K")

    # Test M
    html = "<span>3.1M</span> Pulls"
    assert scraper._parse_pulls(html) == (3100000, "3.1M")

    # Test B
    html = "<span>1.5B</span> Pulls"
    assert scraper._parse_pulls(html) == (1500000000, "1.5B")

    # Test Downloads fallback
    html = "<span>4.2M</span> Downloads"
    assert scraper._parse_pulls(html) == (4200000, "4.2M")

def test_parse_variants():
    scraper = ModelScraper()
    tags_html = """
    <div class="flex items-center">
        <a class="break-all">latest</a>
        <span>4.7 GB</span>
    </div>
    <div class="flex items-center">
        <a class="break-all">8b</a>
        <span>8.5 GB</span>
    </div>
    """
    variants = scraper._parse_variants(tags_html)
    assert len(variants) == 2
    assert variants[0]["tag"] == "latest"
    assert variants[0]["size_text"] == "4.7 GB"
    assert variants[0]["size_bytes"] == int(4.7 * 1024 * 1024 * 1024)

    assert variants[1]["tag"] == "8b"
    assert variants[1]["size_text"] == "8.5 GB"

@pytest.mark.asyncio
async def test_fetch_404(httpx_mock):
    httpx_mock.add_response(url="https://ollama.com/library/notfound", status_code=404)
    httpx_mock.add_response(url="https://ollama.com/library/notfound/tags", status_code=404)

    scraper = ModelScraper()
    result = await scraper.fetch_model_detail("notfound")
    assert result is None

@pytest.mark.asyncio
async def test_fetch_success(httpx_mock):
    httpx_mock.add_response(
        url="https://ollama.com/library/testmodel",
        text="""
        <html><body>
        <span class="break-all">testmodel</span>
        <span>1.1M Pulls</span>
        <span>Tools</span><span>Vision</span>
        <meta name="description" content="Test blurb">
        <div class="prose">Test description</div>
        Updated 2 days ago
        </body></html>
        """
    )
    httpx_mock.add_response(
        url="https://ollama.com/library/testmodel/tags",
        text='<div class="flex items-center"><a class="break-all">latest</a> 4.7 GB</div>'
    )

    scraper = ModelScraper()
    result = await scraper.fetch_model_detail("testmodel")

    assert result is not None
    assert result["slug"] == "testmodel"
    assert result["pulls"] == 1100000
    assert result["pulls_text"] == "1.1M"
    assert "tools" in result["capabilities"]
    assert "vision" in result["capabilities"]
    assert result["blurb"] == "Test blurb"
    assert result["description"] == "Test description"
    assert result["updated"] == "2 days ago"
    assert len(result["variants"]) == 1
    assert result["variants"][0]["tag"] == "latest"
    assert result["model_type"] == "official"
    assert result["namespace"] is None
