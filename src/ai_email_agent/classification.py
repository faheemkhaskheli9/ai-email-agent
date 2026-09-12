"""LLM-backed email classification.

``EmailClassifierClient`` is the swappable boundary (mirrors ``MailboxClient``
in connector.py) — ``OpenAIClassifierClient`` calls the real OpenAI API with a
configurable prompt/schema built from the taxonomy; tests use a fake client so
the pipeline runs with no network access or API key.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from ai_email_agent.taxonomy import Category

logger = logging.getLogger("ai_email_agent.classification")


class ClassificationError(ValueError):
    """Raised when a classifier response can't be trusted.

    A 200-equivalent (a completed API call) tells us nothing about whether the
    payload is usable: the label might not be one of the configured
    categories, or the confidence might not be a real probability. Either is
    treated as a hard failure rather than persisted as if it were valid.
    """


@dataclass(frozen=True)
class ClassificationResult:
    label: str
    confidence: float
    model: str
    classified_at: str  # ISO-8601 UTC timestamp


class EmailClassifierClient(Protocol):
    @property
    def model_name(self) -> str: ...

    def classify(self, subject: str, body: str, categories: list[Category]) -> tuple[str, float]:
        """Return (label, confidence). May raise on API/network failure."""
        ...


def classify_email(
    client: EmailClassifierClient,
    subject: str,
    body: str,
    categories: list[Category],
) -> ClassificationResult:
    """Classify one email and validate the result against the taxonomy.

    Raises :class:`ClassificationError` (never silently accepts a bad result)
    if the label isn't one of ``categories`` or confidence isn't in [0, 1].
    """
    valid_labels = {c.name for c in categories}
    label, confidence = client.classify(subject, body, categories)

    if label not in valid_labels:
        raise ClassificationError(
            f"classifier returned label {label!r}, not one of the configured "
            f"categories {sorted(valid_labels)}"
        )
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ClassificationError(f"classifier returned a non-numeric confidence: {confidence!r}")
    confidence = float(confidence)
    if not (0.0 <= confidence <= 1.0):
        raise ClassificationError(f"classifier returned an out-of-range confidence: {confidence!r}")

    return ClassificationResult(
        label=label,
        confidence=confidence,
        model=client.model_name,
        classified_at=datetime.now(timezone.utc).isoformat(),
    )


class OpenAIClassifierClient:
    """Real classifier: one OpenAI chat-completion call constrained to JSON output.

    Not exercised against the live API by the test suite (no network access,
    no API key committed) — a ``client`` object can be injected to stand in
    for the OpenAI SDK, the same convention ``ImapMailboxClient`` uses for a
    real IMAP connection.
    """

    def __init__(self, api_key: str, *, model: str = "gpt-4o-mini", client: object | None = None) -> None:
        self._model = model
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI  # imported lazily: unused (and unneeded) in tests

            self._client = OpenAI(api_key=api_key)

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, subject: str, body: str, categories: list[Category]) -> tuple[str, float]:
        category_names = [c.name for c in categories]
        schema = {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": category_names},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["label", "confidence"],
            "additionalProperties": False,
        }
        taxonomy_desc = "\n".join(f"- {c.name}: {c.description}" for c in categories)

        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the incoming email into exactly one of these "
                        f"categories:\n{taxonomy_desc}\n\n"
                        "Return the category name and your confidence between 0.0 and 1.0."
                    ),
                },
                {"role": "user", "content": f"Subject: {subject}\n\n{body}"},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "email_classification", "schema": schema, "strict": True},
            },
        )
        content = response.choices[0].message.content
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ClassificationError(f"classifier returned non-JSON content: {content!r}") from exc

        try:
            return payload["label"], payload["confidence"]
        except (KeyError, TypeError) as exc:
            raise ClassificationError(f"classifier response missing expected field: {payload!r}") from exc
