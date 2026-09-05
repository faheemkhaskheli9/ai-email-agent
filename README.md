# Email Response AI Agent

> LLM, RAG & Agentic AI portfolio project — independent open-source implementation.
> This is an original, from-scratch build. It is not affiliated with, and does not
> contain any code, prompts, data, or business logic from, any employer or client.

![status](https://img.shields.io/badge/status-in%20progress-yellow)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## 1. Problem

Support and sales teams get repetitive email volume. An agent that classifies, drafts, and routes responses for human approval can cut response time significantly.

## 2. Architecture

```text
Incoming Email -> Classification -> History Retrieval -> Draft Generation -> Human Approval -> Send
```

## 3. Technology Stack

- Python
- OpenAI API
- IMAP/SMTP or provider API
- PostgreSQL
- FastAPI

## 4. Feature List

- Email classification
- Conversation-history retrieval
- Response generation
- Tone selection
- Structured action extraction (e.g., create ticket)
- Human approval step before sending

## 5. Implementation Plan

1. Phase 1: Email ingestion and classification
2. Phase 2: History-aware response drafting
3. Phase 3: Approval queue UI
4. Phase 4: Structured action extraction and routing
5. Phase 5: Evaluation, observability & deployment

## Task Tracking

Work is broken into phase-tagged user stories tracked as GitHub Issues, not in this file. To see what's open:

    gh issue list --repo faheemkhaskheli9/ai-email-agent --state open --label type:user-story

Implement Phase 1 issues first (later phases depend on it). When you start one, add label `status:in-progress`. When you finish, close it referencing the commit (e.g. `git commit -m "... Closes #4"`) and push.

## 6. Repository Structure

```text
ai-email-agent/
├── README.md
├── LICENSE
├── .gitignore
├── pyproject.toml
├── .env.example
├── docker/
├── docs/
│   ├── architecture.md
│   └── evaluation.md
├── src/
├── tests/
├── configs/
├── scripts/
├── notebooks/
├── examples/
├── assets/
└── .github/
    └── workflows/
```

## 7. Setup

```bash
git clone <this-repo-url>
cd ai-email-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # or: pip install -e .
cp .env.example .env              # fill in API keys / config
```

## 8. Dataset

Document which public dataset(s) or synthetic data generators are used here.
No proprietary, employer-owned, or client-identifiable data is used in this project.

## 9. Training / Execution

Phase 1 ships the mailbox ingestion connector: it normalizes raw email into a
common schema, skips already-ingested messages by `Message-ID`, and logs (never
crashes on) malformed MIME. It runs against a fixture directory of `.eml`
files by default, or a real IMAP mailbox when `IMAP_HOST`/`IMAP_USER`/
`IMAP_PASSWORD` are set:

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m ai_email_agent.cli poll --mailbox examples/sample_mailbox --verbose
```

## 10. Evaluation

Document evaluation metrics and how to reproduce them here (see `docs/evaluation.md`).

## 11. Results

_To be filled in as the implementation progresses — screenshots, metrics tables, and
sample outputs go here._

## 12. API

_If this project exposes an API, document the main endpoints here (or link to
auto-generated OpenAPI docs, e.g. `/docs` for FastAPI)._

## 13. Docker

```bash
docker build -t ai-email-agent .
docker run -p 8000:8000 ai-email-agent
```

## 14. Tests

```bash
pytest tests/
```

## 15. Limitations

- This is a from-scratch, independent recreation built for portfolio purposes.
- Performance numbers, once added, are based on public datasets and are not
  representative of any production system's real-world results.

## 16. Future Work

- Expand evaluation coverage and add CI-based regression checks.
- Add more configuration presets and deployment targets.
- Track open items as GitHub Issues.

## 17. Disclosure

This repository is an **independent open-source recreation inspired by the kind of
production systems I have worked on professionally**. It contains no employer or
client source code, prompts, datasets, credentials, architecture diagrams, or
business logic. All code, data, and documentation here are original or built on
publicly available datasets and open-source tools.

---
_Last updated: 2026-08-18_
