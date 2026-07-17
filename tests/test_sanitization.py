import json

from ollama_catalog.sanitization import (
    REDACTED_CREDENTIAL,
    REDACTED_EMAIL,
    REDACTED_INTERNAL_URL,
    REDACTED_PRIVATE_IP,
    REDACTED_PRIVATE_KEY,
    sanitize_model_record,
    sanitize_models_jsonl,
    sanitize_text,
)


def test_sanitize_text_redacts_requested_sensitive_categories():
    value = """email person@example.com api_key=abc123 password: hunter2 https://localhost:11434/x 192.168.1.5
-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"""
    result = sanitize_text(value)
    for marker in (REDACTED_EMAIL, REDACTED_CREDENTIAL, REDACTED_INTERNAL_URL, REDACTED_PRIVATE_IP, REDACTED_PRIVATE_KEY):
        assert marker in result
    assert "person@example.com" not in result
    assert "hunter2" not in result


def test_sanitize_model_record_preserves_schema_and_sanitizes_untrusted_values():
    model = {
        "slug": "owner/model",
        "name": "model",
        "namespace": "owner",
        "model_type": "base",
        "capabilities": ["chat"],
        "pulls": 42,
        "pulls_text": "42",
        "updated": "today",
        "tags_count": 1,
        "description": "token: abc",
        "blurb": "mail a@b.example",
        "variants": [{"tag": "token: nested", "context": "https://localhost:11434"}],
        "future_text": "password: secret",
    }
    result = sanitize_model_record(model)
    for field in ("slug", "name", "namespace", "model_type", "capabilities", "pulls", "pulls_text", "updated", "tags_count"):
        assert result[field] == model[field]
    assert REDACTED_CREDENTIAL in result["description"]
    assert REDACTED_EMAIL in result["blurb"]
    assert REDACTED_CREDENTIAL in result["variants"][0]["tag"]
    assert REDACTED_INTERNAL_URL in result["variants"][0]["context"]
    assert REDACTED_CREDENTIAL in result["future_text"]
    assert model["description"] == "token: abc"


def test_sanitize_models_jsonl_replaces_file_atomically_and_is_idempotent(tmp_path):
    path = tmp_path / "models.jsonl"
    original = {"slug": "owner/model", "description": "password: secret"}
    path.write_text(json.dumps(original) + "\n", encoding="utf-8")

    result = sanitize_models_jsonl(path)
    assert result.records == 1
    assert result.changed == 1
    assert REDACTED_CREDENTIAL in path.read_text(encoding="utf-8")
    assert not list(tmp_path.glob(".models.jsonl.*.tmp"))
    assert sanitize_models_jsonl(path).changed == 0


def test_sanitize_models_jsonl_preserves_original_when_replacement_fails(tmp_path, monkeypatch):
    path = tmp_path / "models.jsonl"
    original = json.dumps({"slug": "owner/model", "description": "password: secret"}) + "\n"
    path.write_text(original, encoding="utf-8")

    def replacement_failure(self, target):
        raise OSError("replacement failed")

    monkeypatch.setattr(type(path), "replace", replacement_failure)

    try:
        sanitize_models_jsonl(path)
    except OSError as error:
        assert str(error) == "replacement failed"
    else:
        raise AssertionError("expected replacement to fail")

    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".models.jsonl.*.tmp"))
