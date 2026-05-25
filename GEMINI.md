# Gemini CLI Instructions -- rag_processor

## Repository Context

This is a Python package (rag_processor) providing a RAG pipeline with FastAPI backend
integration. The package is managed with `uv`, linted with Ruff, type-checked with
BasedPyright, and tested with pytest.

See `CLAUDE.md` for full project standards. This file captures the subset of rules most
relevant to Gemini CLI and other non-Claude coding agents.

## Tool Mapping

Gemini CLI uses its own built-in tools (Read, Write, Edit, Bash, etc.). Consult the
Gemini CLI documentation for tool names; they differ from Claude Code equivalents.

## Writing Rules

Never use em-dashes in any output. Replace with comma, semicolon, or colon.

## Branch Naming

`feat/<description>` for features, `fix/<description>` for bug fixes. Never commit
directly to `main`.

## Code Quality

- Formatter: `uv run ruff format .`
- Linter: `uv run ruff check . --fix`
- Type checker: `uv run basedpyright src/`
- Tests: `uv run pytest --cov=src --cov-fail-under=80`
- Run `pre-commit run --all-files` before any commit.

## Security

- Never suppress security scanner findings without a documented justification.
- Use `uv run pip-audit` to check for vulnerable dependencies.
- Follow FIPS 140-2/140-3 patterns described in `CLAUDE.md`.
