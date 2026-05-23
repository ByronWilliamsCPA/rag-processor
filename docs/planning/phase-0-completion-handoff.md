---
title: "Phase 0 Completion Handoff"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Handoff to a second team to resolve the remaining Phase 0 gaps and bring all CI checks green."
component: Development-Tools
source: "Phase 0 completion planning"
tags:
  - ci_cd
  - infrastructure
---

**Project**: rag-processor
**Repository**: [github.com/ByronWilliamsCPA/rag-processor](https://github.com/ByronWilliamsCPA/rag-processor)
**Branch**: `main`
**Prepared by**: Byron Williams / Claude Code
**Date**: 2026-05-23

---

## Summary

Phase 0 foundation work is 90% complete. All application code, Docker Compose
services, pre-commit hooks, and the main CI workflow are in place and passing.
Three CI workflows were broken, and one required project file was missing. All
three CI failures trace to two root causes, so fixing two things unblocks
everything.

No application code changes are needed for Phase 0 completion.

---

## What Is Already Working

These items are verified passing and require no action:

- **CI workflow** (`ci.yml`): 334 tests, 82.95% coverage, all checks pass
- **SonarCloud, CodeQL, Security Analysis**: passing on `main`
- **REUSE Compliance**: passing
- **Codecov, Qlty, Coverage**: all passing
- **Postman API Tests (Newman)**: passing
- **Pre-commit hooks**: trailing whitespace, YAML/JSON/TOML validation, TruffleHog, Bandit,
  conventional commits, interrogate, darglint all configured
- **Docker Compose**: app + PostgreSQL + Redis + RQ worker + cloudflared + React frontend
  services defined
- **Ruff (`src/` scope)**: `All checks passed!`
- **BasedPyright**: `0 errors`

---

## Failing CI Checks (3 total, 2 root causes)

### Root Cause A: `SECURITY.md` is missing

**Affected workflow**: OpenSSF Scorecard (`scorecard.yml`)
**CI result**: `failure` (OpenSSF Scorecard)

The OpenSSF Scorecard tool grades the repository on supply chain security
criteria. One of the first checks it runs is whether a `SECURITY.md` file
exists at the repo root. It is a required file under both the OpenSSF
baseline and this project's own CLAUDE.md standards.

**Verification command** (run from repo root):

```bash
ls SECURITY.md
# Before this PR:  ls: cannot access 'SECURITY.md': No such file or directory
# After this PR:   SECURITY.md
```

### Fix A: Create `SECURITY.md`

Create the file at the repository root with at minimum the following content.
Adjust the contact email and version numbers to match the project:

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities by emailing **byron@williamscpa.dev** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigation

You will receive a response within 72 hours. If the vulnerability is
confirmed, a fix will be prioritised and you will be credited in the
release notes unless you prefer otherwise.

## Security Scanning

This project runs automated security checks on every pull request:

- Bandit (Python static analysis)
- TruffleHog (secret detection)
- CodeQL (semantic code analysis)
- pip-audit / OSV Scanner (dependency vulnerability scanning)
- Trivy (container image scanning)

See `.github/workflows/security-analysis.yml` for configuration.
```

After creating the file, commit it with a conventional commit message:

```bash
git add SECURITY.md
git commit -m "docs: add SECURITY.md security policy"
git push origin main
```

The Scorecard workflow triggers on every push to `main` and will re-run
automatically. A clean run does not guarantee a perfect score, but the
missing-file failure will be resolved.

---

### Root Cause B: PyPI Trusted Publishing is not configured

**Affected workflows**:

- Semantic Release (`release.yml`): `failure`
- SLSA Provenance (`slsa-provenance.yml`): `failure` (cascades from Semantic Release)

The Semantic Release workflow is configured with `publish-to-pypi: true` and
targets `https://upload.pypi.org/legacy/`. It attempts to publish the
`rag-processor` package to PyPI on every push to `main`. Because no PyPI
project exists and no Trusted Publishing environment is configured, the upload
step fails. SLSA Provenance runs only when Semantic Release succeeds (gated
by `if: github.event.workflow_run.conclusion == 'success'`), so it also
fails as a cascade.

**Evidence from CI log**:

```text
Release Pipeline / Build & Release
  publish-to-pypi: true
  pypi-package-name: rag-processor
  pypi-url: https://upload.pypi.org/legacy/
```

### Fix B, Option 1: Configure PyPI Trusted Publishing (recommended)

This is the correct long-term fix. PyPI Trusted Publishing uses GitHub's OIDC
token; no API key is needed.

**Step 1**: Create the PyPI project.

Log in to [pypi.org](https://pypi.org) and create a new project named
`rag-processor`. If the name is taken, pick an available name and update
`pypi-package-name` in `.github/workflows/release.yml` to match.

**Step 2**: Add a Trusted Publisher on PyPI.

Go to the project's publishing settings on PyPI
(`https://pypi.org/manage/project/rag-processor/settings/publishing/`) and
add a GitHub Actions trusted publisher with these values:

| Field             | Value              |
| ----------------- | ------------------ |
| Owner             | `ByronWilliamsCPA` |
| Repository        | `rag-processor`    |
| Workflow filename | `release.yml`      |
| Environment name  | `pypi`             |

The environment name must match the one configured in the org reusable workflow.

**Step 3**: Create a `pypi` environment in the GitHub repository.

Go to **Settings > Environments > New environment** and create an environment
named `pypi`. No secrets are needed; the OIDC token is issued automatically.

**Step 4**: Push a commit that triggers a release.

The project is at version `0.1.0`. Semantic Release looks for commits since
the last git tag. Because no tag exists yet, it will detect all `feat:` and
`fix:` commits and attempt a release. Push any `fix:` commit to trigger the
workflow. Alternatively, use the manual `workflow_dispatch` trigger in GitHub
Actions with `force_release: patch` to force a `0.1.1` release.

### Fix B, Option 2: Disable PyPI publishing temporarily (applied)

This option was applied in this PR. `.github/workflows/release.yml` now has
`publish-to-pypi: false`. Semantic Release will still run and create GitHub
Releases and tags, but will skip the PyPI upload. SLSA Provenance succeeds
because Semantic Release passes.

> Note: Option 2 leaves the PyPI integration incomplete. Option 1 is the
> correct finish for Phase 0.

---

## Minor Issue: Ruff Scans `.worktrees/`

**Severity**: Low. Does not affect CI, but causes noise when running
`uv run ruff check .` locally.

Running ruff from the repository root picks up files in `.worktrees/`, which
is the git worktree directory for branch checkouts. This produces 26 spurious
errors in `.worktrees/…/benchmark.py`.

**Verification command**:

```bash
uv run ruff check .
# Before this PR:  26 errors, all in .worktrees/
# After this PR:   All checks passed!
# uv run ruff check src/ shows: All checks passed!
```

### Fix: Add `.worktrees/` to the ruff exclude list

In `pyproject.toml`, find the `[tool.ruff]` section and add `.worktrees` to
the `exclude` list:

```toml
[tool.ruff]
exclude = [
    ".git",
    ".mypy_cache",
    ".worktrees",   # add this line
    # ... rest of existing excludes
]
```

After this change, both `uv run ruff check .` and `uv run ruff check src/`
will return `All checks passed!`.

---

## Acceptance Criteria

Phase 0 is complete when all of the following pass in a single CI run on
`main`:

| Check                    | Current     | Target      |
| ------------------------ | ----------- | ----------- |
| CI (tests + coverage)    | passing     | passing     |
| SonarCloud               | passing     | passing     |
| Security Analysis        | passing     | passing     |
| REUSE Compliance         | passing     | passing     |
| CodeQL                   | passing     | passing     |
| Postman API Tests        | passing     | passing     |
| **OpenSSF Scorecard**    | **failing** | **passing** |
| **Semantic Release**     | **failing** | **passing** |
| **SLSA Provenance**      | **failing** | **passing** |

Verify with:

```bash
gh run list --limit 10 --json status,conclusion,name \
  | python3 -c "import json,sys; [print(f'{r[\"conclusion\"]:10} {r[\"name\"]}') for r in json.load(sys.stdin)]"
```

All entries should read `success`.

---

## Order of Operations

1. Create `SECURITY.md` and push to `main` (fixes Scorecard)
2. Configure PyPI Trusted Publishing and `pypi` GitHub environment, or set
   `publish-to-pypi: false` temporarily (fixes Semantic Release and SLSA)
3. Optionally add `.worktrees/` to the ruff exclude list (removes local noise)
4. Confirm all three previously failing workflows are now green on `main`

Items 1 and 2 are independent and can be done in parallel. Item 3 can be
batched into either commit.

---

## Context for the Receiving Team

### Repository access

The repository is at
[github.com/ByronWilliamsCPA/rag-processor](https://github.com/ByronWilliamsCPA/rag-processor).
All CI uses the org-level reusable workflows at
`ByronWilliamsCPA/.github/.github/workflows/` pinned to
`1b2d33c47cc11a96b9757b49f41873c54e75f57c`.

### Python environment

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -q

# Run linter (scoped to src/ to avoid .worktrees/ noise)
uv run ruff check src/

# Run type checker
uv run basedpyright src/
```

### Commit requirements

All commits must be conventional commits and must pass the pre-commit hooks:

```bash
pre-commit run --all-files   # before committing
```

Examples of valid commit messages:

```text
docs: add SECURITY.md security policy
ci: disable PyPI publish until trusted publishing is configured
chore: exclude .worktrees from ruff scan
```

### What NOT to change

Do not modify any application source code in `src/`, test files in `tests/`,
or `docker-compose.yml` during Phase 0 completion. Changes in this handoff
are limited to:

- `SECURITY.md` (new file)
- `.github/workflows/release.yml` (one-line change if Option 2)
- `pyproject.toml` (one-line addition to ruff exclude)

---

## Questions

Direct questions about this handoff to Byron Williams (`byron@williamscpa.dev`)
or open an issue on the repository with the label `phase-0`.
