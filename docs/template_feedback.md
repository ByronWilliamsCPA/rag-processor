---
title: "Template Feedback"
schema_type: common
status: published
owner: core-maintainer
purpose: "Document template issues for upstream fixes."
tags:
  - feedback
  - template
---

> **Purpose**: Document issues discovered in this project that should be addressed in the [cookiecutter-python-template](https://github.com/ByronWilliamsCPA/cookiecutter-python-template).
>
> **Generated From**: cookiecutter-python-template v0.1.0
> **Project Created**: __PROJECT_CREATION_DATE__

---

## How to Use This File

When working on this project, if you discover any issue that originates from the template itself (not project-specific), add it here with the following format:

```markdown
### [Short Title]

- **Priority**: Critical / High / Medium / Low
- **Category**: [Configuration / Documentation / Tooling / Structure / CI/CD / Security / Other]
- **Discovered**: YYYY-MM-DD

**Issue**: [Clear description of what's wrong or missing]

**Context**: [How was this discovered? What were you trying to do?]

**Suggested Fix**: [What should the template do differently?]

**Affected Files**: [List template files that need changes]
```

---

## Feedback Items

<!-- Add your feedback below this line -->

### Org reusable workflow callers do not set `no-build: false`

- **Priority**: High
- **Category**: CI/CD
- **Discovered**: 2026-05-20

**Issue**: The generated workflows under `.github/workflows/` call the org reusable workflows in `ByronWilliamsCPA/.github` without setting `no-build: false`. The org workflows default `no-build` to `true`, which passes `--no-build` to `uv sync`. With a `hatchling.build` backend (the template default) and editable install of the project package, that command fails:

```
error: Distribution `<project>==0.1.0 @ editable+.` can't be installed because it is marked as `--no-build` but has no binary distribution
```

Every workflow that syncs project deps (CI, PR validation, compatibility matrix, performance regression, docs, sonarcloud, sbom, mutation, release, security-analysis) is broken until each caller adds `no-build: false`.

**Context**: Discovered while pinning org reusable workflow refs from `@main` to a SHA on PR #27 of rag-processor. The bump exposed the failure because the older SHA pre-dated the `--no-build` default.

**Suggested Fix**: In the cookiecutter template, render every reusable-workflow caller with `no-build: false` in its `with:` block whenever the cookie cutter chooses a build backend that requires building the local project (hatchling, setuptools editable, etc.). Alternatively, change the org workflows to default `no-build: false`, or detect a local editable install and skip `--no-build` for the project root.

**Affected Files**: `{{cookiecutter.project_slug}}/.github/workflows/{ci,pr-validation,python-compatibility,performance-regression,docs,sonarcloud,sbom,mutation-testing,release,security-analysis}.yml`

---

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.
