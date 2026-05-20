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

### PYSEC-2025-183

| Field | Value |
| --- | --- |
| **Advisory ID** | PYSEC-2025-183 |
| **Package** | `pyjwt` 2.12.1 |
| **Affected versions** | All released versions (range: introduced from 0, no fix event) |
| **Severity** | Disputed |
| **First documented** | 2026-05-20 |
| **Reassess by** | 2026-07-19 |
| **Status** | Disputed by vendor; no fix planned |

**Vulnerability summary**: Per the OSV record (CVE-2025-45768): "pyjwt v2.10.1 was
discovered to contain weak encryption. NOTE: this is disputed by the Supplier
because the key length is chosen by the application that uses the library
(admittedly, library users may benefit from a minimum value and a mechanism
for opting in to strict enforcement)."

**Why it cannot be fixed**: There is no upstream fix because the vendor disputes
that this is a vulnerability. Key length is the caller's responsibility, not
the library's. `pyjwt` 2.12.1 is the latest released version.

**Exposure assessment**: Authentication flows in this project use pyjwt for
JWT signing and verification. The cited "weak encryption" concern is about
short symmetric keys, which the caller controls. This project does not expose
key-length selection to untrusted input; keys come from configured secrets.
Risk is not applicable.

**Reassessment checklist**:

- [ ] Check whether OSV/NVD has withdrawn or reclassified the advisory
- [ ] Verify pyjwt continues to be maintained and does not introduce an
      opt-in minimum-key-length feature that would require adoption
- [ ] Re-run `uv run pip-audit` to confirm the advisory still applies
- [ ] Update or remove this entry and the `pyproject.toml` ignore entry accordingly

---

### PYSEC-2026-89

| Field | Value |
| --- | --- |
| **Advisory ID** | PYSEC-2026-89 (CVE-2025-69534, GHSA-5wmx-573v-2qwq) |
| **Package** | `markdown` 3.10 |
| **Affected versions** | OSV record asserts "all versions" (events: introduced=0, no fix event) |
| **Severity** | Medium (DoS in apps parsing untrusted Markdown) |
| **First documented** | 2026-05-20 |
| **Reassess by** | 2026-07-19 |
| **Status** | Stale OSV record; fix already in our installed version |

**Vulnerability summary**: Per the OSV record: "Python-Markdown version 3.8
contain a vulnerability where malformed HTML-like sequences can cause
html.parser.HTMLParser to raise an unhandled AssertionError during Markdown
parsing... The issue was acknowledged by the vendor and fixed in version 3.8.1."

**Why it cannot be fixed (and why ignoring is correct)**: The advisory text
explicitly states the fix landed in `markdown` 3.8.1. This project has
`markdown` 3.10 installed, which is newer than the documented fix. However,
the structured `events` field in the OSV record is malformed (the second
event is `{}` instead of `{"fixed": "3.8.1"}`), so pip-audit's range
comparison incorrectly flags every version as vulnerable. There is no
package change that resolves this; the database entry itself is broken.

**Exposure assessment**: The vulnerable code path (parsing untrusted Markdown)
does not apply: this project uses `markdown` only as a transitive dependency
of `mkdocs-material` for building documentation from trusted in-repo content.
No untrusted Markdown is parsed at runtime.

**Reassessment checklist**:

- [ ] Check whether the OSV record's `events` field has been corrected to
      include `{"fixed": "3.8.1"}` (which would cause pip-audit to clear
      the flag automatically)
- [ ] Re-run `uv run pip-audit` to confirm the advisory still applies
- [ ] Update or remove this entry and the `pyproject.toml` ignore entry accordingly

---

## Resolved Entries

| Advisory ID | Package | Fixed in | Resolution date |
| --- | --- | --- | --- |
| CVE-2026-1703 | `pip` 25.3 | `pip` 26.1.1 | 2026-05-11 |
| CVE-2026-3219 | `pip` 25.3 | `pip` 26.1.1 | 2026-05-11 |
| CVE-2026-6357 | `pip` 25.3 | `pip` 26.1.1 | 2026-05-11 |
