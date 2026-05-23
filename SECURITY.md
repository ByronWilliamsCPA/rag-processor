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
