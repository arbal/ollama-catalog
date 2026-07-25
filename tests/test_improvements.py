import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch
from bs4 import BeautifulSoup
from ollama_catalog.model_scraper import ModelScraper
from ollama_catalog.catalog import CatalogFetcher

def test_url_encoding_special_characters():
    scraper = ModelScraper()
    # verify that special characters are encoded while slashes are preserved
    assert scraper.detect_url("user space/model name") == "https://ollama.com/user%20space/model%20name"
    assert scraper.detect_url("official model@123") == "https://ollama.com/library/official%20model%40123"

def test_pulls_parsing_overflow_and_value_error():
    scraper = ModelScraper()
    # Extremely large float/int string that might overflow, or weird malformed text
    val, text = scraper._parse_pulls("<span>1.5e308 Pulls</span>")
    assert val == 0
    assert text == "0"

    val2, text2 = scraper._parse_pulls("<span>invalid Pulls</span>")
    assert val2 == 0
    assert text2 == "0"

@pytest.mark.asyncio
async def test_fetch_url_retries_on_status_errors(httpx_mock):
    # Mock a transient 503 error, followed by 200 OK
    httpx_mock.add_response(url="https://ollama.com/library/test-transient", status_code=503)
    httpx_mock.add_response(url="https://ollama.com/library/test-transient", status_code=200, text="success")

    scraper = ModelScraper()
    # Since we have tenacity retry, calling _fetch_url should retry after 503 and return the 200 OK response!
    response = await scraper._fetch_url("https://ollama.com/library/test-transient")
    assert response.status_code == 200
    assert response.text == "success"

@pytest.mark.asyncio
async def test_fetch_url_does_not_retry_on_404(httpx_mock):
    httpx_mock.add_response(url="https://ollama.com/library/test-404", status_code=404)

    scraper = ModelScraper()
    # Should not raise exception or retry, should just return the 404 response
    response = await scraper._fetch_url("https://ollama.com/library/test-404")
    assert response.status_code == 404

def test_catalog_load_with_malformed_jsonl(tmp_path):
    models_file = tmp_path / "models.jsonl"
    pulls_file = tmp_path / "pulls.jsonl"

    # Write one valid line and one malformed line
    models_file.write_text(
        '{"slug": "valid/model", "name": "model", "model_type": "community"}\n'
        'invalid_json_line_here\n'
    )
    pulls_file.write_text(
        '{"slug": "valid/model", "pulls": 100, "pulls_text": "100"}\n'
        '{"slug": "malformed_no_json", \n'
    )

    # Patch the paths in CatalogFetcher
    with patch("ollama_catalog.catalog.MODELS_JSONL", models_file), \
         patch("ollama_catalog.catalog.PULLS_JSONL", pulls_file):
        fetcher = CatalogFetcher()
        catalog_data = fetcher.load_existing_catalog()

        # Should gracefully skip malformed lines and load the valid one
        assert catalog_data["model_count"] == 1
        assert catalog_data["models"][0]["slug"] == "valid/model"
