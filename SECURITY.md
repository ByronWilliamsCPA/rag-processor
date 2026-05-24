# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

**Preferred channel -- GitHub Private Vulnerability Reporting (private):**
Use [GitHub's Private Vulnerability Reporting](https://github.com/ByronWilliamsCPA/rag-processor/security/advisories/new)
to submit a report. This channel keeps all details confidential until a fix is released.
Private reporting is preferred over email because it keeps the disclosure timeline
and patch coordination private.

**Secondary channel -- encrypted email:**
If you cannot use GitHub's advisory form, email **<byron@williamscpa.dev>** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigation

**Response SLA:**
We commit to acknowledging all vulnerability reports within 14 days of submission
(typically within 72 hours). If the vulnerability is confirmed, a fix will be
prioritized and you will be credited in the release notes unless you prefer otherwise.

## Security Surface

This repository contains a RAG (Retrieval-Augmented Generation) pipeline with a
FastAPI backend and React-based frontend. Primary security concerns and mitigations:

| Attack vector | Mitigation |
| --- | --- |
| **JWT validation** -- Cloudflare Access tokens verified via JWKS | `pyjwt` with JWKS URI; algorithm allow-list enforced; token claims validated on every request |
| **File upload handling** -- PDF ingestion via `pdfplumber` and `python-magic` | File-type detection before parsing; size limits enforced; uploads processed in isolated job queue workers |
| **SSRF in httpx client** -- outbound HTTP calls to user-supplied or config-driven URLs | Allowlist of permitted host patterns; private-network CIDR ranges blocked; redirects disabled by default |
| **Redis/RQ job queue** -- deserialization of job payloads | Payloads are structured dicts validated by Pydantic before execution; no `pickle` used for job arguments |
| **Supply-chain posture** | GitHub Actions pinned to full commit SHAs; Renovate for automated dependency updates; Sigstore-signed releases; org-level rulesets enforce required status checks and secret scanning |

Security scanning runs on every pull request and weekly on a schedule. See the
"Security Scanning" section below for tooling details.

## Security Scanning

This project runs automated security checks on every pull request:

- Bandit (Python static analysis)
- TruffleHog (secret detection)
- CodeQL (semantic code analysis)
- pip-audit / OSV Scanner (dependency vulnerability scanning)
- Trivy (container image scanning)

See `.github/workflows/security-analysis.yml` for configuration.
