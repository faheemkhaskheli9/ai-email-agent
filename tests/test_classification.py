import json
from datetime import datetime

import pytest

from ai_email_agent.classification import (
    ClassificationError,
    OpenAIClassifierClient,
    classify_email,
)
from ai_email_agent.taxonomy import Category, load_categories

CATEGORIES = load_categories()

# One fixture email per configured category (Phase 1 acceptance criterion).
FIXTURE_EMAILS = {
    "support": ("Trouble logging in", "Hi, I can't log into my account since yesterday."),
    "sales": ("Pricing for enterprise plan", "Hi, we're evaluating your product for 200 seats."),
    "billing": ("Wrong amount charged", "You charged me twice for last month's invoice."),
    "spam": ("You won a prize!!!", "Click here now to claim your free reward."),
}


class FakeClassifierClient:
    """Returns a canned (label, confidence) pair — no network access needed."""

    def __init__(self, label: str, confidence: float = 0.9, model: str = "fake-model-v1") -> None:
        self._label = label
        self._confidence = confidence
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, subject: str, body: str, categories: list[Category]) -> tuple[str, float]:
        return self._label, self._confidence


@pytest.mark.parametrize("label", sorted(FIXTURE_EMAILS))
def test_classifies_one_fixture_email_per_category(label: str):
    subject, body = FIXTURE_EMAILS[label]
    client = FakeClassifierClient(label)

    result = classify_email(client, subject, body, CATEGORIES)

    assert result.label == label
    assert result.confidence == pytest.approx(0.9)
    assert result.model == "fake-model-v1"
    # Must be a parseable ISO-8601 timestamp.
    datetime.fromisoformat(result.classified_at)


def test_label_not_in_taxonomy_raises():
    client = FakeClassifierClient("not-a-real-category")
    with pytest.raises(ClassificationError, match="not one of the configured categories"):
        classify_email(client, "subject", "body", CATEGORIES)


@pytest.mark.parametrize("bad_confidence", [-0.1, 1.5, "high", True])
def test_invalid_confidence_raises(bad_confidence):
    client = FakeClassifierClient("support", confidence=bad_confidence)
    with pytest.raises(ClassificationError):
        classify_email(client, "subject", "body", CATEGORIES)


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("Message", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeChatCompletions(content)


class _FakeOpenAISDK:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def test_openai_classifier_client_parses_json_schema_response():
    payload = json.dumps({"label": "billing", "confidence": 0.87})
    sdk = _FakeOpenAISDK(payload)
    client = OpenAIClassifierClient("fake-key", client=sdk)

    label, confidence = client.classify("subject", "body", CATEGORIES)

    assert label == "billing"
    assert confidence == pytest.approx(0.87)
    # A category taxonomy was actually sent to the model, not hardcoded.
    sent_categories = sdk.chat.completions.last_kwargs["response_format"]["json_schema"]["schema"][
        "properties"
    ]["label"]["enum"]
    assert sent_categories == [c.name for c in CATEGORIES]


def test_openai_classifier_client_raises_on_non_json_content():
    sdk = _FakeOpenAISDK("not json")
    client = OpenAIClassifierClient("fake-key", client=sdk)
    with pytest.raises(ClassificationError, match="non-JSON content"):
        client.classify("subject", "body", CATEGORIES)


def test_openai_classifier_client_raises_on_missing_field():
    sdk = _FakeOpenAISDK(json.dumps({"label": "billing"}))
    client = OpenAIClassifierClient("fake-key", client=sdk)
    with pytest.raises(ClassificationError, match="missing expected field"):
        client.classify("subject", "body", CATEGORIES)
