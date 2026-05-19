# AGENTS.md

> Agent conventions for the RAG Processor project.
> Spec: https://agents.md

## Project Overview

RAG Processor is a FastAPI backend that powers a retrieval-augmented generation
pipeline. It exposes a REST/WebSocket API consumed by a React frontend. Key
subsystems: document ingestion, vector search routing, queue-based async
processing (RQ + Redis), structured logging with correlation IDs, and
OWASP-aligned security middleware.

Entry point: `src/rag_processor/main.py`

## Code Style

- **Language**: Python 3.12
- **Formatter**: `ruff format` (line length 88)
- **Linter**: `ruff check` (PyStrict-aligned rule set; no ignored rules without a
  documented reason and tracking reference)
- **Type checker**: `basedpyright` in strict mode
- Never introduce `# noqa`, `# type: ignore`, or `# pyright: ignore` without a
  companion comment explaining the suppression and a ticket reference.
- No em-dash characters (U+2014) anywhere: in code comments, docstrings, commit messages, or
  documentation. Use a comma, semicolon, or colon instead.
- Docstrings follow Google style.

## Test Commands

```bash
# Run full suite with coverage gate
uv run pytest --cov=src --cov-fail-under=80

# Run with branch coverage report
uv run pytest --cov=src --cov-report=html --cov-branch

# Run a single test
uv run pytest tests/unit/test_example.py::test_function_name -v
```

Coverage thresholds: 80% line, 70% branch, 90% for critical paths and new patches.

## Security Gates

Run these before every commit and in CI:

```bash
uv run bandit -r src                 # Static security analysis
uv run pip-audit                     # Dependency vulnerability scan
uv run ruff check .                  # Linting (includes security rules)
uv run basedpyright src/             # Type checking
pre-commit run --all-files           # All hooks
```

Unfixed CVEs must be documented in `docs/known-vulnerabilities.md` using the
template at `docs/known-vulnerabilities-template.md`. No entry ages past 60 days
without reassessment.

## Branch Workflow

- **Never commit directly to `main`**. Always work on a feature branch.
- Branch naming: `{type}/{descriptive-slug}`

| Type | Prefix | Example |
|------|--------|---------|
| New feature | `feat/` | `feat/vector-search-api` |
| Bug fix | `fix/` | `fix/correlation-id-leak` |
| Docs | `docs/` | `docs/api-reference` |
| Refactor | `refactor/` | `refactor/queue-retry-logic` |
| Tests | `test/` | `test/integration-auth` |
| Chore | `chore/` | `chore/compliance-sweep` |

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) and
must be GPG-signed.

Worktrees go inside the project at `.worktrees/<branch-slug>` (never at global
paths). The `.worktrees/` directory is git-ignored.

## Architecture Notes

- Configuration: Pydantic Settings (`src/rag_processor/core/config.py`); use
  `.env` files; never hard-code secrets.
- Exceptions: use the hierarchy in `src/rag_processor/core/exceptions.py`; do
  not raise bare `Exception`.
- Logging: structured JSON via `src/rag_processor/utils/logging.py`; all logs
  in a request context include the correlation ID automatically.
- Security middleware: `src/rag_processor/middleware/security.py` (OWASP
  headers); add to every FastAPI app instance.
- FIPS compliance: use `hashlib.md5(data, usedforsecurity=False)` for
  non-security hashes; use SHA-256 or better for security purposes.

## Response-Aware Development

Tag assumptions that could cause production failures:

```python
# #CRITICAL: [category]: [assumption]
# #VERIFY: [what to validate]

# #ASSUME: [category]: [assumption]
# #VERIFY: [validation needed]
```

Mandatory categories: timing dependencies, external resources, data integrity,
concurrency, security, payment/financial.
