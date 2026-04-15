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
    # Generates mock HTML containing the slugs
    return " ".join([f'<span class="x-test-search-response-title"> {slug} </span>' for slug in slugs])

@pytest.mark.asyncio
async def test_slug_deduplication(state_manager):
    scraper = DiscoveryScraper(state_manager=state_manager)
    # Only test a single query for simplicity
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["model1", "model2"]),
        mock_html(["model2", "model3"]),  # model2 is duplicated
        ""  # Empty to stop pagination
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert len(discovered) == 3
    assert set(discovered) == {"model1", "model2", "model3"}
    assert mock_fetch.call_count == 3

@pytest.mark.asyncio
async def test_incremental_stop_logic(state_manager):
    # Set incremental_stop to 2 for faster test
    state_manager.incremental_stop = 2
    state_manager.mark_seen("seen_model")

    scraper = DiscoveryScraper(state_manager=state_manager)
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["new_model"]),
        mock_html(["seen_model"]), # Page 2: 1st consecutive seen
        mock_html(["seen_model"]), # Page 3: 2nd consecutive seen -> should stop
        mock_html(["unseen_model"]) # Should not be reached
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert set(discovered) == {"new_model"}
    assert mock_fetch.call_count == 3

@pytest.mark.asyncio
async def test_limit_flag(state_manager):
    scraper = DiscoveryScraper(state_manager=state_manager, limit=2)
    # Using 2 queries to test global limit across concurrent tasks
    scraper.queries = ['a']

    mock_responses = [
        mock_html(["model1", "model2", "model3", "model4"]),
        ""
    ]

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = mock_responses
        discovered = await scraper.run()

    assert len(discovered) == 2
    assert "model1" in discovered or "model2" in discovered
