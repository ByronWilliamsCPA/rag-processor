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
> **Project Created**: **PROJECT_CREATION_DATE**

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

**Issue**: The generated workflows under `.github/workflows/` call the org reusable workflows in
`ByronWilliamsCPA/.github` without setting `no-build: false`. The org workflows default `no-build` to `true`, which
passes `--no-build` to `uv sync`. With a `hatchling.build` backend (the template default) and editable install of the
project package, that command fails:

```text
error: Distribution `<project>==0.1.0 @ editable+.` can't be installed because it is marked as `--no-build` but has no binary distribution
```

Every workflow that syncs project deps (CI, PR validation, compatibility matrix, performance regression, docs,
sonarcloud, sbom, mutation, release, security-analysis) is broken until each caller adds `no-build: false`.

**Context**: Discovered while pinning org reusable workflow refs from `@main` to a SHA on PR #27 of rag-processor. The
bump exposed the failure because the older SHA pre-dated the `--no-build` default.

**Suggested Fix**: In the cookiecutter template, render every reusable-workflow caller with `no-build: false` in its
`with:` block whenever the cookie cutter chooses a build backend that requires building the local project (hatchling,
setuptools editable, etc.). Alternatively, change the org workflows to default `no-build: false`, or detect a local
editable install and skip `--no-build` for the project root.

**Affected Files** (all under `{{cookiecutter.project_slug}}/.github/workflows/`):

- `ci.yml`
- `pr-validation.yml`
- `python-compatibility.yml`
- `performance-regression.yml`
- `docs.yml`
- `sonarcloud.yml`
- `sbom.yml`
- `mutation-testing.yml`
- `release.yml`
- `security-analysis.yml`

### Stale `sonar-organization` default in sonarcloud.yml

- **Priority**: Medium
- **Category**: CI/CD
- **Discovered**: 2026-05-20

**Issue**: The generated `.github/workflows/sonarcloud.yml` passes `sonar-organization: 'williaby'` to the org reusable
workflow. That value is a leftover personal handle, not the GitHub org. The matching `sonar-project.properties` is
rendered with the actual org (`byronwilliamscpa`), and the project key with the actual GitHub owner
(`ByronWilliamsCPA_*`). The org-key mismatch causes `sonar-scanner` to exit 3 - the project literally does not exist
under `williaby`.

**Context**: Issue #8 of rag-processor was opened to track SonarCloud failures; root cause was this template default.

**Suggested Fix**: Derive `sonar-organization` from a cookiecutter variable - either lowercase
`cookiecutter.github_owner` or a dedicated `cookiecutter.sonar_organization` - so the workflow and the properties file
agree out of the box.

**Affected Files**: `{{cookiecutter.project_slug}}/.github/workflows/sonarcloud.yml`

### `test-command` with embedded quotes word-splits in org workflow

- **Priority**: Medium
- **Category**: CI/CD
- **Discovered**: 2026-05-20

**Issue**: The template ships `.github/workflows/python-compatibility.yml` with `test-command: 'pytest ... -m "not slow
and not integration"'`. The org reusable workflow expands `$TEST_COMMAND` unquoted, so the embedded `"` are kept as
literal bytes and bash word-splits the marker expression into separate args. pytest then receives `-m "not slow and not
integration"` as six fragmented arguments and rejects them with exit 4.

The template also ignores `tests/load`, which it doesn't generate.

**Context**: Discovered while migrating org workflow pins from `@main` to a fixed SHA.

**Suggested Fix**: Either (a) drop the `-m` filter from the default test-command (and let projects add it back if they
actually have slow-marked tests), (b) replace the spaced marker expression with a single-word custom marker like
`excluded_from_compat`, or (c) have the org workflow wrap `$TEST_COMMAND` in `bash -c` so embedded quotes are honored.
Also remove the `--ignore=tests/load` default since that directory isn't generated.

**Affected Files**: `{{cookiecutter.project_slug}}/.github/workflows/python-compatibility.yml`

### `atheris` dev dep has no wheel for Python 3.10

- **Priority**: Medium
- **Category**: Tooling
- **Discovered**: 2026-05-20

**Issue**: The template's dev extras pin `atheris>=2.3.0`. uv resolves this to 3.0.0, which ships wheels only for
cp311/cp312/cp313. On Python 3.10 the install attempts to build from sdist, which requires Clang and a matching
libFuzzer toolchain - that build fails in stock CI runners. Meanwhile the template's `requires-python = ">=3.10,..."`
and `python-compatibility.yml` matrix both claim Python 3.10 support, so the matrix's 3.10 leg fails before tests run.

`atheris` is not imported anywhere in the generated source/tests/scripts of this project, so the dep was effectively
dead weight gating compatibility testing.

**Context**: Discovered on PR #27 of rag-processor while bringing the compatibility matrix green.

**Suggested Fix**: Either (a) drop `atheris` from the default dev extras (templates should not bundle deps they never
use), (b) mark it `; python_version >= '3.11'` so 3.10 stays installable, or (c) drop Python 3.10 from the default
`python-compatibility.yml` matrix and tighten `requires-python` to `>=3.11`.

**Affected Files**: `{{cookiecutter.project_slug}}/pyproject.toml`, optionally
`{{cookiecutter.project_slug}}/.github/workflows/python-compatibility.yml`

---

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.
