import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from ollama_catalog.scraper import DiscoveryScraper
from ollama_catalog.state import StateManager

@pytest.fixture
def temp_state_file(tmp_path):
    return tmp_path / "seen_slugs.json"

@pytest.fixture
def state_manager(temp_state_file):
    return StateManager(state_file=temp_state_file, incremental_stop=3)

def mock_html(slugs):
    # Matches the live Ollama search-result anchor contract.
    return " ".join([f'<a href="/{slug}" class="group w-full"> {slug} </a>' for slug in slugs])

@pytest.mark.asyncio
async def test_slug_deduplication(state_manager):
    scraper = DiscoveryScraper(state_manager=state_manager)
    # Only test a single query for simplicity
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["owner/model1", "owner/model2"]),
        mock_html(["owner/model2", "owner/model3"]),  # model2 is duplicated
        ""  # Empty to stop pagination
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert len(discovered) == 3
    assert set(discovered) == {"owner/model1", "owner/model2", "owner/model3"}
    assert mock_fetch.call_count == 3

@pytest.mark.asyncio
async def test_incremental_stop_logic(state_manager):
    # Set incremental_stop to 2 for faster test
    state_manager.incremental_stop = 2
    state_manager.mark_seen("owner/seen_model")

    scraper = DiscoveryScraper(state_manager=state_manager)
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["owner/new_model"]),
        mock_html(["owner/seen_model"]), # Page 2: 1st consecutive seen
        mock_html(["owner/seen_model"]), # Page 3: 2nd consecutive seen -> should stop
        mock_html(["owner/unseen_model"]) # Should not be reached
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert set(discovered) == {"owner/new_model"}
    assert mock_fetch.call_count == 3

@pytest.mark.asyncio
async def test_full_coverage_reaches_unseen_slug_after_seen_pages(state_manager):
    state_manager.incremental_stop = 2
    state_manager.mark_seen("owner/seen_model")

    scraper = DiscoveryScraper(state_manager=state_manager, full_mode=True)
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["owner/seen_model"]),
        mock_html(["owner/seen_model"]),
        mock_html(["owner/unseen_model"]),
        "",
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert set(discovered) == {"owner/unseen_model"}
    assert scraper.observed_slugs == {"owner/seen_model", "owner/unseen_model"}
    assert state_manager.seen_slugs == {"owner/seen_model", "owner/unseen_model"}
    assert mock_fetch.call_count == 4

@pytest.mark.asyncio
async def test_limit_flag(state_manager):
    scraper = DiscoveryScraper(state_manager=state_manager, limit=2)
    # Using 2 queries to test global limit across concurrent tasks
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["owner/model1", "owner/model2", "owner/model3", "owner/model4"]),
        ""
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert len(discovered) == 2
    assert "owner/model1" in discovered or "owner/model2" in discovered

def test_parse_live_search_result_links(state_manager):
    scraper = DiscoveryScraper(state_manager=state_manager)
    html = (
        '<a href="/download" class="group w-full">Download</a>'
        '<a href="/library/gemma4" class="group w-full">gemma4</a>'
        '<a href="/example/model" class="group w-full">model</a>'
    )

    assert scraper._parse_slugs(html) == ["library/gemma4", "example/model"]
