---
title: "Reusable Workflow Issues - Handoff Document"
schema_type: common
status: published
owner: core-maintainer
purpose: "Document reusable workflow issues for the .github team to resolve."
tags:
  - ci_cd
  - reference
  - infrastructure
---

**Project**: rag-processor
**PR**: [#4](https://github.com/ByronWilliamsCPA/rag-processor/pull/4)
**Date**: 2025-12-16
**Prepared by**: Claude Code (assisted)

---

## Executive Summary

During CI runs for PR #4 (Phase 1 Core Features), several reusable workflows from the `ByronWilliamsCPA/.github` repository are failing. These failures are **not caused by the project code** but by issues in the shared workflow definitions.

**Key Finding**: The `rag-processor` project uses `python-magic` which requires the `libmagic` system library. This dependency is not available by default on GitHub's macOS/Windows runners, and the reusable workflows don't provide a mechanism to install system dependencies before running tests.

### Workflows Status Summary

| Workflow | Status | Issue Type |
|----------|--------|------------|
| Python Compatibility | ✅ Passing* | *Disabled macOS/Windows locally |
| Container Security | ✅ Passing | Fixed with `.trivyignore` |
| Dependency Review | ✅ Fixed | Was local project config error (fixed) |
| Performance Regression | ✅ Passing | Now working (may have been transient) |
| SonarCloud Analysis | ❌ Failing | Missing `--all-extras` |
| ClusterFuzzLite | ❌ Failing | Known org workflow issue |

---

## Issue 1: Dependency Review - Invalid License Configuration (RESOLVED)

> **UPDATE**: This was a **local project configuration error**, not an org workflow issue.
> The project's `.github/workflows/dependency-review.yml` was specifying both `allow-licenses`
> and `deny-licenses`. Fixed by removing `allow-licenses` and keeping only `deny-licenses`.

**Workflow**: `dependency-review.yml` (local project workflow)
**Status**: ✅ Fixed
**Run ID**: 20275824651 (original failure)

**Error Message**:

```text
[
  {
    "code": "custom",
    "message": "You cannot specify both allow-licenses and deny-licenses",
    "path": []
  }
]
```

**Root Cause**:

The workflow passes both `allow-licenses` and `deny-licenses` parameters to `actions/dependency-review-action@v4`, which is not allowed by the action.

**Current Configuration** (from logs):

```yaml
with:
  fail-on-severity: high
  deny-licenses: GPL-3.0, AGPL-3.0, GPL-2.0
  allow-licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, LGPL-2.1, LGPL-3.0, Python-2.0, Unlicense, CC0-1.0
```

**Suggested Fix**:

Use only **one** of these parameters. Recommended approach using `deny-licenses` only:

```yaml
with:
  fail-on-severity: high
  deny-licenses: GPL-3.0, AGPL-3.0, GPL-2.0
  # Remove allow-licenses - action will allow all licenses except denied ones
```

Or use `allow-licenses` only (more restrictive):

```yaml
with:
  fail-on-severity: high
  allow-licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, LGPL-2.1, LGPL-3.0, Python-2.0, Unlicense, CC0-1.0
  # Remove deny-licenses - action will reject all licenses except allowed ones
```

**Reference**:

- [dependency-review-action documentation](https://github.com/actions/dependency-review-action#configuration-options)

---

## Issue 2: Performance Regression - Multiple Issues (NOW PASSING)

> **UPDATE**: This workflow is now passing. The issues may have been transient or
> resolved upstream. Keeping documentation for reference in case issues recur.

**Workflow**: `python-performance-regression.yml` (or equivalent)
**Status**: ✅ Now Passing
**Run ID**: 20275824765 (original failure)

**Error Messages**:

```text
benchmark.py: error: unrecognized arguments: --output /tmp/pr_benchmark.json
⚠️ Benchmark execution failed, creating fallback results
NameError: name 'regression_threshold' is not defined. Did you mean: 'regression_detected'?
```

**Root Causes**:

- **Issue 2a**: The workflow expects benchmark scripts to accept `--output <path>` argument, but this interface is not documented and project benchmark scripts may not implement it.
- **Issue 2b**: The workflow has a Python `NameError` - the variable `regression_threshold` is used but not defined. This is a bug in the workflow itself.

**Suggested Fixes**:

**For Issue 2a** - Document the expected benchmark script interface:

```python
# Expected interface for scripts/benchmark.py
# Should accept: --output <path> --iterations <n>
# Should output JSON: {"p95_ms": float, "p99_ms": float, "throughput_rps": float}
```

Or modify the workflow to handle scripts that output to stdout:

```yaml
- name: Run benchmark
  run: |
    # Try with --output first, fall back to stdout capture
    if uv run python scripts/benchmark.py --help 2>&1 | grep -q -- '--output'; then
      uv run python scripts/benchmark.py --output /tmp/benchmark.json
    else
      uv run python scripts/benchmark.py > /tmp/benchmark.json
    fi
```

**For Issue 2b** - Fix the undefined variable in the workflow:

```python
# Before (broken)
if regression_threshold > some_value:

# After (define the variable or use correct name)
regression_threshold = 0.10  # 10% threshold
# or use the existing variable
if regression_detected:
```

---

## Issue 3: SonarCloud Analysis - Missing Dependencies

**Workflow**: `python-sonarcloud.yml` (or equivalent)
**Status**: `failure`
**Run ID**: 20275824797

**Error Messages**:

```text
collected 279 items / 4 errors
ImportError while importing test module '.../tests/unit/test_auth_middleware.py'.
E   ModuleNotFoundError: No module named 'fastapi'
```

**Root Cause**:

The workflow runs `uv sync` without `--all-extras`, so optional dependencies like `fastapi` are not installed. The tests require these dependencies.

**Current Flow** (from logs):

```yaml
- name: Install dependencies
  run: uv sync  # Missing --all-extras
```

**Suggested Fix**:

Update dependency installation to include all extras:

```yaml
- name: Install dependencies
  run: uv sync --all-extras
```

Or add an input parameter to control this:

```yaml
inputs:
  install-all-extras:
    description: 'Install all optional dependencies'
    type: boolean
    default: true

steps:
  - name: Install dependencies
    run: |
      if [ "${{ inputs.install-all-extras }}" == "true" ]; then
        uv sync --all-extras
      else
        uv sync
      fi
```

---

## Issue 4: Python Compatibility - System Dependencies (Feature Request)

**Workflow**: `python-compatibility.yml`
**Status**: Passing (with workaround)
**Impact**: macOS and Windows testing disabled

### Background

The `rag-processor` project uses `python-magic` for MIME type detection, which requires the `libmagic` system library:

- **Ubuntu**: Pre-installed on GitHub runners
- **macOS**: Requires `brew install libmagic`
- **Windows**: Requires libmagic DLL installation

### Current Workaround

We disabled macOS and Windows testing in the project's workflow caller:

```yaml
# .github/workflows/python-compatibility.yml
jobs:
  compatibility:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml@main
    with:
      include-macos: false   # Disabled: python-magic requires libmagic
      include-windows: false # Disabled: python-magic requires libmagic DLL
```

### Feature Request

Add support for pre-test system dependency installation. Suggested implementation:

```yaml
inputs:
  system-deps-macos:
    description: 'Homebrew packages to install on macOS (space-separated)'
    type: string
    required: false
    default: ''

  system-deps-ubuntu:
    description: 'APT packages to install on Ubuntu (space-separated)'
    type: string
    required: false
    default: ''

  system-deps-windows:
    description: 'Chocolatey packages to install on Windows (space-separated)'
    type: string
    required: false
    default: ''

# In the job steps, before "Install dependencies":
- name: Install system dependencies (macOS)
  if: runner.os == 'macOS' && inputs.system-deps-macos != ''
  run: brew install ${{ inputs.system-deps-macos }}

- name: Install system dependencies (Ubuntu)
  if: runner.os == 'Linux' && inputs.system-deps-ubuntu != ''
  run: sudo apt-get update && sudo apt-get install -y ${{ inputs.system-deps-ubuntu }}

- name: Install system dependencies (Windows)
  if: runner.os == 'Windows' && inputs.system-deps-windows != ''
  run: choco install ${{ inputs.system-deps-windows }}
```

### Usage Example

```yaml
# Project's workflow caller
jobs:
  compatibility:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml@main
    with:
      system-deps-macos: 'libmagic'
      system-deps-ubuntu: ''  # Already installed
      system-deps-windows: 'file'  # Or appropriate package
      include-macos: true
      include-windows: true
```

---

## Issue 5: ClusterFuzzLite - Known Issue

**Workflow**: `clusterfuzzlite.yml`
**Status**: `failure`

This appears to be a pre-existing issue documented in `docs/ci-workflow-issues-handoff.md`. Please refer to that document for details on the ClusterFuzzLite action SHA issues.

---

## Projects Successfully Using These Workflows

For reference, the following projects are reported to be using these reusable workflows successfully:

- (Please add project names that work correctly)

The `rag-processor` project may have unique requirements due to:

1. Use of `python-magic` (requires system library)
2. Use of FastAPI in optional dependencies
3. Custom benchmark script interface

---

## Recommended Priority

1. ~~**High**: Issue 1 (Dependency Review) - Simple config fix~~ ✅ **RESOLVED** (was local project issue)
2. **High**: Issue 3 (SonarCloud) - Simple fix, blocking code analysis
3. ~~**Medium**: Issue 2 (Performance Regression) - Code bug + interface issue~~ ✅ **NOW PASSING**
4. **Low**: Issue 4 (System Dependencies) - Feature request, has workaround

---

## Contact

If you need additional context, CI run logs, or assistance testing fixes:

- Repository: <https://github.com/ByronWilliamsCPA/rag-processor>
- PR: <https://github.com/ByronWilliamsCPA/rag-processor/pull/4>
- Maintainer: Byron Williams

---

## Appendix: Relevant CI Run Links

| Workflow | Run ID | Link |
|----------|--------|------|
| Dependency Review | 20275824651 | [View Run](https://github.com/ByronWilliamsCPA/rag-processor/actions/runs/20275824651) |
| Performance Regression | 20275824765 | [View Run](https://github.com/ByronWilliamsCPA/rag-processor/actions/runs/20275824765) |
| SonarCloud Analysis | 20275824797 | [View Run](https://github.com/ByronWilliamsCPA/rag-processor/actions/runs/20275824797) |
| Python Compatibility | 20275824720 | [View Run](https://github.com/ByronWilliamsCPA/rag-processor/actions/runs/20275824720) |
