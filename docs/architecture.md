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
