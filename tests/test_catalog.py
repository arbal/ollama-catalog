import pytest
from unittest.mock import AsyncMock, patch
import json
import asyncio
from ollama_catalog.catalog import CatalogFetcher

@pytest.fixture
def catalog_output_paths(tmp_path):
    """Redirect every catalog artifact so tests never modify tracked output."""
    return {
        "catalog": tmp_path / "ollama_catalog.json",
        "discovered": tmp_path / "discovered_slugs.json",
        "models": tmp_path / "models.jsonl",
        "pulls": tmp_path / "pulls.jsonl",
        "metadata": tmp_path / "metadata.json",
    }


def patch_catalog_output_paths(paths):
    return patch.multiple(
        "ollama_catalog.catalog",
        CATALOG_FILE=paths["catalog"],
        DISCOVERED_FILE=paths["discovered"],
        MODELS_JSONL=paths["models"],
        PULLS_JSONL=paths["pulls"],
        METADATA_JSON=paths["metadata"],
    )

@pytest.mark.asyncio
async def test_run_preserves_existing_models(catalog_output_paths):
    catalog_file = catalog_output_paths["catalog"]
    discovered_file = catalog_output_paths["discovered"]

    # Pre-populate catalog
    with open(catalog_file, "w") as f:
        json.dump({
            "models": [{"slug": "existing_model", "name": "existing_model"}]
        }, f)

    with open(discovered_file, "w") as f:
        json.dump(["new_model"], f)

    with patch_catalog_output_paths(catalog_output_paths):

        fetcher = CatalogFetcher()
        fetcher.scraper.fetch_model_detail = AsyncMock(return_value={"slug": "new_model", "name": "new_model", "pulls_text": "1", "capabilities": []})

        await fetcher.run()

        with open(catalog_file, "r") as f:
            data = json.load(f)
            slugs = [m["slug"] for m in data["models"]]
            assert "existing_model" in slugs
            assert "new_model" in slugs

@pytest.mark.asyncio
async def test_incremental_save_does_not_wipe_catalog(catalog_output_paths):
    catalog_file = catalog_output_paths["catalog"]
    discovered_file = catalog_output_paths["discovered"]

    with open(catalog_file, "w") as f:
        json.dump({
            "models": [{"slug": "old_model", "name": "old_model"}]
        }, f)

    with open(discovered_file, "w") as f:
        # Create 50 slugs to trigger incremental save
        json.dump([f"new_{i}" for i in range(50)], f)

    with patch_catalog_output_paths(catalog_output_paths):

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
async def test_missing_discovered_file_requires_discovery(catalog_output_paths):
    catalog_output_paths["discovered"] = catalog_output_paths["discovered"].with_name("missing.json")

    with patch_catalog_output_paths(catalog_output_paths):
        fetcher = CatalogFetcher()
        with pytest.raises(FileNotFoundError, match="ollama-catalog discover"):
            fetcher.load_discovered()
