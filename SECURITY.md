# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| < 0.1.0 | No |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.** Public
disclosure before a fix is available puts all users at risk.

### Primary Channel

Use [GitHub Private Vulnerability Reporting](https://github.com/ByronWilliamsCPA/rag-processor/security/advisories/new)
to submit a confidential report. GitHub keeps the report private until a
coordinated disclosure date is agreed upon.

### Backup Channel

If you are unable to use GitHub's private reporting feature, email
[byron@williamscpa.dev](mailto:byron@williamscpa.dev) with the subject line
`SECURITY: <short summary>`. Encrypt the message with the maintainer's public
key if you need to share sensitive details.

## Response SLA

We commit to acknowledging all vulnerability reports within 14 days of submission.

After acknowledgement, the typical response timeline is:

| Stage | Target |
| --- | --- |
| Initial triage (severity assessment) | Within 7 days of acknowledgement |
| Fix development and testing | Within 60 days of triage (critical: 14 days) |
| Coordinated disclosure and release | On or before the disclosure date agreed with reporter |

The maintainer may request an extension if the vulnerability requires significant
refactoring. Any extension will be communicated to the reporter before the
original deadline expires.

## Security Surface

RAG Processor is a Python 3.12 FastAPI backend with React frontend integration
for a RAG (Retrieval Augmented Generation) pipeline. The application accepts
user-supplied documents, passes them through a processing pipeline backed by
Redis and PostgreSQL, and returns structured results.

### Primary Attack Vectors

| Vector | Description |
| --- | --- |
| Dependency supply-chain attacks | Third-party packages introduced via pip or uv that contain malicious code or known CVEs |
| Credential exposure in workflow files | Secrets accidentally committed to `.github/workflows/` or surfaced in CI logs |
| Prompt injection via user-supplied RAG input | User-controlled text that manipulates LLM behavior or exfiltrates context window contents |
| Authentication bypass in the FastAPI layer | Unauthenticated access to protected API endpoints via malformed tokens or missing checks |
| Template injection in agent prompts | User-controlled data that escapes prompt templates and alters agent instructions |
| Path traversal in file uploads | Malformed file paths in uploaded documents that traverse outside the `/data` directory |

### Active Mitigations

- **Secret scanning and push protection**: Enabled at the repository level; GitHub
  blocks pushes containing detected secrets before they reach the remote.
- **Required-status-check rulesets**: Branch protection enforced via org-level
  rulesets; merges require CI and security checks to pass.
- **Bandit SAST**: Static analysis runs on every pull request; high-severity
  findings block merge.
- **pip-audit dependency scanning**: Runs in CI; known CVEs block release.
  Unfixable CVEs are documented in
  [`docs/known-vulnerabilities.md`](docs/known-vulnerabilities.md) and reviewed
  quarterly. No entry ages past 60 days without reassessment.
- **Trufflehog pre-commit hook**: Scans every commit locally for credential
  patterns before they reach the remote repository.
- **Signed commits**: All maintainer commits are GPG-signed; required by the
  branch protection ruleset.
- **Branch protection rulesets**: Enforced at the org level; direct pushes to
  `main` are blocked and required status checks must pass before merge.
- **OWASP security headers middleware**: Adds Content-Security-Policy,
  X-Content-Type-Options, and related headers to every API response.
- **Correlation ID tracing**: All requests carry a correlation ID for
  audit-trail reconstruction.
- **ClusterFuzzLite**: Continuous fuzzing runs in CI to surface edge-case
  crashes and input-handling vulnerabilities.

## Coordinated Disclosure

The default disclosure window is 90 days from the date of the initial report,
or upon the public release of a fix, whichever is sooner. If the reporter
requests a shorter window or the vulnerability is being actively exploited,
the window may be shortened after mutual agreement.

Security advisories are published via
[GitHub Security Advisories](https://github.com/ByronWilliamsCPA/rag-processor/security/advisories).

---

## OpenSSF Best Practices Artifacts

**OpenSSF Best Practices Badge**: Pending application at
[bestpractices.coreinfrastructure.org](https://bestpractices.coreinfrastructure.org/en/projects/new).
Once registered, the badge and criteria completion status will appear in the README.

**CHANGELOG format for security fixes**: Security fixes that have an assigned CVE
must cite it in the changelog entry using the format:

```
- fix(security): resolve CVE-YYYY-NNNNN -- <brief description>
```

Example: `- fix(security): resolve CVE-2024-12345 -- reject malformed JWT headers in auth middleware`.

Unfixable CVEs with documented risk assessments are tracked in
[`docs/known-vulnerabilities.md`](docs/known-vulnerabilities.md). No CVE entry
ages past 60 days without reassessment; the OpenSSF release gate blocks releases
for any vulnerability older than 60 days.
