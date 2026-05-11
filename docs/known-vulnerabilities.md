---
title: "Known Vulnerabilities"
schema_type: common
status: published
owner: core-maintainer
purpose: "Documented CVEs that cannot be immediately resolved, per project vulnerability policy."
tags:
  - security
  - dependencies
---

Vulnerabilities that cannot be immediately resolved are documented here per project policy.
Each entry must be reassessed quarterly; no entry ages past 60 days without reassessment.
The OpenSSF release gate blocks releases for any vulnerability older than 60 days regardless
of reassessment status.

The corresponding `[tool.pip-audit]` ignore entries in `pyproject.toml` suppress CI failures
for the listed advisory IDs. Entries must be removed from both files once a fix is available.

---

## Active Entries

### PYSEC-2022-42969

| Field | Value |
| --- | --- |
| **Advisory ID** | PYSEC-2022-42969 |
| **Package** | `py` 1.11.0 |
| **Affected versions** | All released versions |
| **Severity** | Medium |
| **First documented** | 2026-05-11 |
| **Reassess by** | 2026-07-11 |
| **Status** | No fix available |

**Vulnerability summary**: The `py` library has a path traversal issue affecting its
`svnwc.py` component. It is not used in this project for SVN operations; the dependency
is pulled in transitively.

**Why it cannot be fixed**: `py` 1.11.0 is a transitive dependency of `interrogate` 1.7.0
(docstring coverage enforcement tool). `interrogate` is pinned to its latest release
(1.7.0); no newer version exists that drops the `py` dependency or pins a patched version.
Removing `interrogate` would eliminate docstring coverage gates from the development toolchain.

**Exposure assessment**: `py`'s `svnwc.py` is not imported or invoked anywhere in this
project. The vulnerable code path requires direct use of the SVN working-copy API, which
this project does not perform. Risk is negligible in this context.

**Reassessment checklist**:

- [ ] Check for a new `interrogate` release that removes `py` as a dependency
- [ ] Check PyPI for a patched `py` release
- [ ] Re-run `uv run pip-audit` to confirm whether the advisory still applies
- [ ] Update or remove this entry and the `pyproject.toml` ignore entry accordingly

---

## Resolved Entries

| Advisory ID | Package | Fixed in | Resolution date |
| --- | --- | --- | --- |
| CVE-2026-1703 | `pip` 25.3 | `pip` 26.1.1 | 2026-05-11 |
| CVE-2026-3219 | `pip` 25.3 | `pip` 26.1.1 | 2026-05-11 |
| CVE-2026-6357 | `pip` 25.3 | `pip` 26.1.1 | 2026-05-11 |
