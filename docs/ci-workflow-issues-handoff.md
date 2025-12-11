---
title: "CI Workflow Issues - Handoff Document"
schema_type: common
status: published
owner: core-maintainer
purpose: "Document CI workflow issues in the organization's reusable workflows for GitHub team."
tags:
  - ci_cd
  - reference
  - infrastructure
---

**Project**: rag-processor
**PR**: [#3](https://github.com/ByronWilliamsCPA/rag-processor/pull/3)
**Date**: 2025-12-11
**Prepared by**: Claude Code (assisted)

---

## Summary

During CI runs for PR #3 (Phase 0 Infrastructure), several reusable workflows from the `ByronWilliamsCPA/.github` organization repository are failing due to configuration issues. These failures are **not caused by the project code** but by problems in the shared workflow definitions.

---

## Issue 1: FIPS Compatibility Check - Invalid Action SHA

**Workflow**: `python-fips-compatibility.yml` (or similar)
**Status**: `startup_failure`
**Run ID**: 20148614888

### Error (Issue 1)

```text
##[error]An action could not be found at the URI 'https://api.github.com/repos/astral-sh/setup-uv/tarball/582b2d78a0f5913301dcc87c4e93301fdd2b6711'
```

### Root Cause (Issue 1)

The workflow references a specific SHA (`582b2d78a0f5913301dcc87c4e93301fdd2b6711`) for `astral-sh/setup-uv` that does not exist or is no longer valid.

### Suggested Fix (Issue 1)

Update the action reference to use a valid version tag or SHA:

```yaml
# Before (broken)
- uses: astral-sh/setup-uv@582b2d78a0f5913301dcc87c4e93301fdd2b6711

# After (use latest stable tag)
- uses: astral-sh/setup-uv@v4
# Or pin to a known working SHA
```

---

## Issue 2: ClusterFuzzLite - Invalid Action SHA

**Workflow**: `clusterfuzzlite.yml`
**Status**: `startup_failure`
**Run ID**: 20148614891

### Error (Issue 2)

```text
##[error]An action could not be found at the URI 'https://api.github.com/repos/google/clusterfuzzlite/tarball/f090cc7d581f82fb0e0b04f0c9e56ff7f4a24e76'
```

### Root Cause (Issue 2)

The workflow references a specific SHA for `google/clusterfuzzlite` that does not exist or has been removed.

### Suggested Fix (Issue 2)

Update to a valid ClusterFuzzLite action reference:

```yaml
# Before (broken)
- uses: google/clusterfuzzlite@f090cc7d581f82fb0e0b04f0c9e56ff7f4a24e76

# After (use main branch or valid tag)
- uses: google/clusterfuzzlite@main
# Or use the official OSS-Fuzz action
- uses: google/oss-fuzz/infra/cifuzz/actions/run_fuzzers@master
```

---

## Issue 3: Python Compatibility Matrix - Multiline Output Bug

**Workflow**: `python-compatibility.yml`
**Status**: `failure`
**Run ID**: 20148614958

### Error (Issue 3)

```text
##[error]Unable to process file command 'output' successfully.
##[error]Invalid format '  "python": ['
```

### Root Cause (Issue 3)

The workflow generates a JSON matrix and writes it to `$GITHUB_OUTPUT`, but the multiline JSON format breaks GitHub Actions' output parsing.

### Current Code (Problematic - Issue 3)

```bash
MATRIX=$(jq -n \
  --argjson python '["3.10", "3.11", "3.12", "3.13"]' \
  --argjson os "$OS_LIST" \
  '{python: $python, os: $os}')

echo "matrix=$MATRIX" >> $GITHUB_OUTPUT
```

### Suggested Fix (Issue 3)

Use compact JSON output or the heredoc delimiter syntax:

```bash
# Option 1: Compact JSON (single line)
MATRIX=$(jq -c -n \
  --argjson python '["3.10", "3.11", "3.12", "3.13"]' \
  --argjson os "$OS_LIST" \
  '{python: $python, os: $os}')
echo "matrix=$MATRIX" >> $GITHUB_OUTPUT

# Option 2: Heredoc syntax for multiline
echo "matrix<<EOF" >> $GITHUB_OUTPUT
echo "$MATRIX" >> $GITHUB_OUTPUT
echo "EOF" >> $GITHUB_OUTPUT
```

---

## Issue 4: Dependency Review - Conflicting License Configuration

**Workflow**: `dependency-review.yml` (or caller workflow)
**Status**: `failure`
**Run ID**: 20148614894

### Error (Issue 4)

```json
[
  {
    "code": "custom",
    "message": "You cannot specify both allow-licenses and deny-licenses",
    "path": []
  }
]
```

### Root Cause (Issue 4)

The workflow passes both `allow-licenses` and `deny-licenses` to the `actions/dependency-review-action`, which is not allowed.

### Current Configuration (Problematic - Issue 4)

```yaml
- uses: actions/dependency-review-action@v4
  with:
    fail-on-severity: high
    deny-licenses: GPL-3.0, AGPL-3.0, GPL-2.0
    allow-licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, LGPL-2.1, LGPL-3.0, Python-2.0, Unlicense, CC0-1.0
```

### Suggested Fix (Issue 4)

Use only one of `allow-licenses` OR `deny-licenses`, not both:

```yaml
# Option 1: Deny-list approach (block specific licenses)
- uses: actions/dependency-review-action@v4
  with:
    fail-on-severity: high
    deny-licenses: GPL-3.0, AGPL-3.0, GPL-2.0

# Option 2: Allow-list approach (only permit specific licenses)
- uses: actions/dependency-review-action@v4
  with:
    fail-on-severity: high
    allow-licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, LGPL-2.1, LGPL-3.0, Python-2.0, Unlicense, CC0-1.0
```

---

## Issue 5: SonarCloud Analysis - Execution Failure

**Workflow**: `sonarcloud.yml`
**Status**: `failure`
**Run ID**: 20148614860

### Error (Issue 5)

```text
EXECUTION FAILURE
```

### Likely Root Causes (Issue 5)

1. Missing `SONAR_TOKEN` secret in the repository
2. Missing or misconfigured `sonar-project.properties` file
3. SonarCloud project not properly configured for the repository

### Suggested Fixes (Issue 5)

1. Ensure `SONAR_TOKEN` is set as a repository or organization secret
2. Verify `sonar-project.properties` exists and contains:

   ```properties
   sonar.projectKey=ByronWilliamsCPA_rag-processor
   sonar.organization=byronwilliamscpa
   ```

3. Check SonarCloud dashboard to ensure the project is properly linked

---

## Workflows That Passed

For reference, these workflows are working correctly:

| Workflow | Status |
|----------|--------|
| Validate Cruft Status | ✅ Passed |
| Mutation Testing | ✅ Passed |

---

## Recommended Actions

### Immediate (High Priority)

1. **Fix astral-sh/setup-uv SHA** in FIPS workflow
2. **Fix jq output format** in Python Compatibility workflow (use `-c` flag)
3. **Remove conflicting license config** in Dependency Review

### Short-term

1. **Fix ClusterFuzzLite SHA** or disable if not needed
2. **Configure SonarCloud** properly or make it optional for new repos

### Best Practices

- Consider using version tags (`@v4`) instead of SHA pins for actions that update frequently
- For SHA pinning, use Dependabot or Renovate to keep them updated
- Add validation in the reusable workflows to fail gracefully with helpful error messages

---

## Files to Update in `ByronWilliamsCPA/.github`

Based on the errors, these workflow files likely need updates:

```text
.github/workflows/
├── python-fips-compatibility.yml    # Fix setup-uv SHA
├── python-compatibility.yml         # Fix jq multiline output
├── clusterfuzzlite.yml              # Fix clusterfuzzlite SHA
├── dependency-review.yml            # Fix license config conflict
└── sonarcloud.yml                   # Add better error handling
```

---

## Contact

If you need additional context or CI run logs, please reach out. The PR #3 run logs contain full details of each failure.
