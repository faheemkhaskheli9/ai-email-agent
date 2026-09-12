# Architecture Notes: Email Response AI Agent

## Pipeline

```text
Incoming Email -> Classification -> History Retrieval -> Draft Generation -> Human Approval -> Send
```

## Components

- Email classification
- Conversation-history retrieval
- Response generation
- Tone selection
- Structured action extraction (e.g., create ticket)
- Human approval step before sending

## Design Notes

- Keep provider/model choices swappable behind interfaces (see `multi-llm-router`
  and similar projects in this portfolio for the general pattern).
- Prefer configuration-driven pipelines (YAML/JSON in `configs/`) over hardcoded
  parameters so experiments are reproducible.
- A classification below `configs/review.yaml`'s `confidence_threshold`
  (`ai_email_agent.review`) is routed to a `needs_review` status instead of
  `classified` — never let a low-confidence label silently drive a draft or
  routing decision. `PostgresEmailStore.list_by_status` / the
  `review-queue` CLI command is the queryable list this backs.
