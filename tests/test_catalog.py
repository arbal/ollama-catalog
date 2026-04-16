import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import json
import asyncio
from ollama_catalog.catalog import CatalogFetcher

@pytest.fixture
def mock_catalog_files(tmp_path):
    catalog_file = tmp_path / "ollama_catalog.json"
    discovered_file = tmp_path / "discovered_slugs.json"
    seen_file = tmp_path / "seen_slugs.json"

    with patch("ollama_catalog.catalog.CATALOG_FILE", catalog_file), \
         patch("ollama_catalog.catalog.DISCOVERED_FILE", discovered_file), \
         patch("pathlib.Path.exists", side_effect=lambda: True): # simplified
        yield {
            "catalog": catalog_file,
            "discovered": discovered_file,
            "seen": seen_file
        }

@pytest.mark.asyncio
async def test_run_preserves_existing_models(tmp_path):
    catalog_file = tmp_path / "ollama_catalog.json"
    discovered_file = tmp_path / "discovered_slugs.json"

    # Pre-populate catalog
    with open(catalog_file, "w") as f:
        json.dump({
            "models": [{"slug": "existing_model", "name": "existing_model"}]
        }, f)

    with open(discovered_file, "w") as f:
        json.dump(["new_model"], f)

    with patch("ollama_catalog.catalog.CATALOG_FILE", catalog_file), \
         patch("ollama_catalog.catalog.DISCOVERED_FILE", discovered_file):

        fetcher = CatalogFetcher()
        fetcher.scraper.fetch_model_detail = AsyncMock(return_value={"slug": "new_model", "name": "new_model", "pulls_text": "1", "capabilities": []})

        await fetcher.run()

        with open(catalog_file, "r") as f:
            data = json.load(f)
            slugs = [m["slug"] for m in data["models"]]
            assert "existing_model" in slugs
            assert "new_model" in slugs

@pytest.mark.asyncio
async def test_incremental_save_does_not_wipe_catalog(tmp_path):
    catalog_file = tmp_path / "ollama_catalog.json"
    discovered_file = tmp_path / "discovered_slugs.json"

    with open(catalog_file, "w") as f:
        json.dump({
            "models": [{"slug": "old_model", "name": "old_model"}]
        }, f)

    with open(discovered_file, "w") as f:
        # Create 50 slugs to trigger incremental save
        json.dump([f"new_{i}" for i in range(50)], f)

    with patch("ollama_catalog.catalog.CATALOG_FILE", catalog_file), \
         patch("ollama_catalog.catalog.DISCOVERED_FILE", discovered_file):

        fetcher = CatalogFetcher()
        fetcher.scraper.fetch_model_detail = AsyncMock(return_value={"slug": "mock", "pulls_text": "1", "capabilities": []})

        # We'll just run it. It should save implicitly at 50 models
        await fetcher.run()

        # Check that old_model is still there
        with open(catalog_file, "r") as f:
            data = json.load(f)
            slugs = [m["slug"] for m in data["models"]]
            assert "old_model" in slugs


@pytest.mark.asyncio
async def test_missing_discovered_file_handled_gracefully(tmp_path):
    catalog_file = tmp_path / "ollama_catalog.json"
    discovered_file = tmp_path / "missing.json"  # Ensure it doesn't exist

    with patch("ollama_catalog.catalog.CATALOG_FILE", catalog_file),          patch("ollama_catalog.catalog.DISCOVERED_FILE", discovered_file):
        fetcher = CatalogFetcher()
        assert fetcher.load_discovered() == []
