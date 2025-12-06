#!/usr/bin/env python3
"""Check code and dependencies for FIPS 140-2/140-3 compatibility issues.

This script detects common patterns and packages that may cause issues when
running on FIPS-enabled systems (like Ubuntu LTS with fips-updates).

FIPS mode restricts cryptographic algorithms to NIST-approved ones:
- Approved: AES, SHA-256/384/512, RSA (2048+), ECDSA, etc.
- Prohibited: MD5, SHA-1 (for signatures), DES, RC4, Blowfish, etc.

Usage:
    python scripts/check_fips_compatibility.py [--strict] [--fix-hints]

Exit codes:
    0: No FIPS compatibility issues found
    1: Issues found (or errors)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

# Known FIPS-incompatible packages
FIPS_INCOMPATIBLE_PACKAGES: dict[str, str] = {
    "pycrypto": "Deprecated and not FIPS-compliant. Use 'pycryptodome' with FIPS mode.",
    "pycryptodome": "Use 'pycryptodomex' for FIPS compliance or ensure FIPS mode is enabled.",
    "m2crypto": "May use non-FIPS OpenSSL. Verify OpenSSL FIPS module is active.",
    "pyopenssl": "Depends on OpenSSL configuration. Ensure FIPS provider is enabled.",
    "paramiko": "Uses cryptography; ensure FIPS-compliant crypto backend.",
    "bcrypt": "bcrypt algorithm is not FIPS-approved. Use PBKDF2 or scrypt instead.",
    "passlib": "Some hashers (bcrypt, argon2) are not FIPS-approved.",
    "itsdangerous": "May use non-FIPS algorithms for signing. Verify configuration.",
}

# Packages that need verification but may be OK
FIPS_VERIFY_PACKAGES: dict[str, str] = {
    "cryptography": "Ensure version >= 3.4.6 and OpenSSL FIPS provider is enabled.",
    "pyca/cryptography": "Ensure version >= 3.4.6 and OpenSSL FIPS provider is enabled.",
    "requests": "Uses urllib3; TLS settings should use FIPS-compliant ciphers.",
    "urllib3": "Ensure TLS 1.2+ with FIPS-approved cipher suites.",
    "httpx": "Verify TLS configuration uses FIPS-approved algorithms.",
    "aiohttp": "Verify TLS configuration uses FIPS-approved algorithms.",
    "boto3": "AWS SDK; ensure FIPS endpoints are used for gov/compliance.",
    "azure-identity": "Azure SDK; ensure FIPS-compliant configuration.",
    "google-cloud-core": "GCP SDK; verify crypto configuration.",
    "jwt": "PyJWT; ensure RS256/ES256 algorithms (not HS256 with weak keys).",
    "pyjwt": "Ensure RS256/ES256 algorithms (not HS256 with weak keys).",
    "python-jose": "Verify algorithm configuration for FIPS compliance.",
}

# Non-FIPS approved hash algorithms
NON_FIPS_HASHES = {"md5", "md4", "sha1", "sha", "ripemd160"}

# Non-FIPS approved ciphers/algorithms
NON_FIPS_CIPHERS = {
    "des",
    "3des",
    "tripledes",
    "rc2",
    "rc4",
    "rc5",
    "blowfish",
    "idea",
    "cast5",
    "seed",
}


@dataclass
class FipsIssue:
    """Represents a FIPS compatibility issue."""

    file_path: Path
    line_number: int
    severity: str  # "error", "warning", "info"
    category: str  # "hash", "cipher", "package", "config"
    message: str
    fix_hint: str | None = None


class FipsCodeVisitor(ast.NodeVisitor):
    """AST visitor to detect FIPS-incompatible code patterns."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.issues: list[FipsIssue] = []
        self._in_hashlib_call = False

    def _check_hashlib_call(self, node: ast.Call, func_name: str) -> None:
        """Check hashlib function calls for FIPS compliance.

        Args:
            node: The AST Call node being checked.
            func_name: The hashlib function name (e.g., 'md5', 'sha1').
        """
        if func_name not in NON_FIPS_HASHES:
            return

        # Check if usedforsecurity=False is set
        if self._has_usedforsecurity_false(node):
            return

        severity = "error" if func_name in {"md5", "md4"} else "warning"
        self.issues.append(
            FipsIssue(
                file_path=self.file_path,
                line_number=node.lineno,
                severity=severity,
                category="hash",
                message=f"hashlib.{func_name}() is not FIPS-approved",
                fix_hint=f"Add usedforsecurity=False if not used for security: "
                f"hashlib.{func_name}(..., usedforsecurity=False)",
            )
        )

    def _has_usedforsecurity_false(self, node: ast.Call) -> bool:
        """Check if usedforsecurity=False is set in call.

        Args:
            node: The AST Call node to check.

        Returns:
            True if usedforsecurity=False is present, False otherwise.
        """
        for keyword in node.keywords:
            if (
                keyword.arg == "usedforsecurity"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is False
            ):
                return True
        return False

    def _check_cipher_usage(self, func_name: str, line_number: int) -> None:
        """Check for non-FIPS cipher usage.

        Args:
            func_name: The cipher function name to check.
            line_number: Source code line number.
        """
        if func_name in NON_FIPS_CIPHERS or any(
            c in func_name for c in NON_FIPS_CIPHERS
        ):
            self.issues.append(
                FipsIssue(
                    file_path=self.file_path,
                    line_number=line_number,
                    severity="error",
                    category="cipher",
                    message=f"Non-FIPS cipher detected: {func_name}",
                    fix_hint="Use AES, ChaCha20-Poly1305, or other FIPS-approved algorithms",
                )
            )

    def _check_new_call(self, node: ast.Call) -> None:
        """Check direct new() calls with algorithm names.

        Args:
            node: The AST Call node with attr 'new'.
        """
        for arg in node.args:
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue

            algo = arg.value.lower()
            if algo not in NON_FIPS_HASHES and algo not in NON_FIPS_CIPHERS:
                continue

            self.issues.append(
                FipsIssue(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    severity="error",
                    category="cipher" if algo in NON_FIPS_CIPHERS else "hash",
                    message=f"Non-FIPS algorithm: {algo}",
                    fix_hint="Use FIPS-approved algorithms (AES, SHA-256, etc.)",
                )
            )

    def _is_hashlib_call(self, node: ast.Call) -> bool:
        """Check if node is a hashlib.* call.

        Args:
            node: The AST Call node to check.

        Returns:
            True if this is a hashlib function call.
        """
        return (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hashlib"
        )

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to detect crypto usage."""
        if not isinstance(node.func, ast.Attribute):
            self.generic_visit(node)
            return

        func_name = node.func.attr.lower()

        # Check for hashlib calls
        if self._is_hashlib_call(node):
            self._check_hashlib_call(node, func_name)

        # Check for Crypto/Cryptodome cipher usage
        self._check_cipher_usage(func_name, node.lineno)

        # Check for direct new() calls with algorithm names
        if node.func.attr == "new":
            self._check_new_call(node)

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check for imports of known problematic modules."""
        for alias in node.names:
            module = alias.name.lower()
            if "crypto" in module and "pycryptodome" not in module:
                if "des" in module or "blowfish" in module or "rc4" in module:
                    self.issues.append(
                        FipsIssue(
                            file_path=self.file_path,
                            line_number=node.lineno,
                            severity="warning",
                            category="cipher",
                            message=f"Import of potentially non-FIPS module: {alias.name}",
                            fix_hint="Verify this module uses FIPS-approved algorithms",
                        )
                    )
        self.generic_visit(node)


def check_python_file(file_path: Path) -> list[FipsIssue]:
    """Check a Python file for FIPS compatibility issues."""
    issues: list[FipsIssue] = []

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        visitor = FipsCodeVisitor(file_path)
        visitor.visit(tree)
        issues.extend(visitor.issues)

    except SyntaxError as e:
        issues.append(
            FipsIssue(
                file_path=file_path,
                line_number=e.lineno or 0,
                severity="warning",
                category="parse",
                message=f"Could not parse file: {e.msg}",
            )
        )
    except Exception as e:
        issues.append(
            FipsIssue(
                file_path=file_path,
                line_number=0,
                severity="warning",
                category="parse",
                message=f"Error reading file: {e}",
            )
        )

    return issues


def _check_package_patterns(
    content: str,
    file_path: Path,
    package: str,
    message: str,
    severity: str,
) -> list[FipsIssue]:
    """Check for package patterns in content and create issues.

    Args:
        content: File content to search.
        file_path: Path to the file being checked.
        package: Package name to search for.
        message: Fix hint message.
        severity: Issue severity level.

    Returns:
        List of FIPS issues found.
    """
    issues: list[FipsIssue] = []
    patterns = [
        rf'"{package}["\s\[<>=]',
        rf"'{package}['\s\[<>=]",
        rf"^{package}\s*[<>=\[]",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                FipsIssue(
                    file_path=file_path,
                    line_number=line_num,
                    severity=severity,
                    category="package",
                    message=f"FIPS-incompatible package: {package}"
                    if severity == "error"
                    else f"Package may need FIPS verification: {package}",
                    fix_hint=message,
                )
            )

    return issues


def check_pyproject_toml(file_path: Path) -> list[FipsIssue]:
    """Check pyproject.toml for FIPS-incompatible dependencies."""
    if not file_path.exists():
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
        issues: list[FipsIssue] = []

        # Check for incompatible packages
        for package, message in FIPS_INCOMPATIBLE_PACKAGES.items():
            issues.extend(
                _check_package_patterns(content, file_path, package, message, "error")
            )

        # Check for packages that need verification
        for package, message in FIPS_VERIFY_PACKAGES.items():
            issues.extend(
                _check_package_patterns(content, file_path, package, message, "info")
            )

        return issues

    except Exception as e:
        return [
            FipsIssue(
                file_path=file_path,
                line_number=0,
                severity="warning",
                category="parse",
                message=f"Error reading pyproject.toml: {e}",
            )
        ]


def check_requirements_file(file_path: Path) -> list[FipsIssue]:
    """Check requirements.txt for FIPS-incompatible dependencies."""
    issues: list[FipsIssue] = []

    if not file_path.exists():
        return issues

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()

        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Extract package name (handle various formats)
            package = re.split(r"[<>=\[\s#]", line)[0].lower()

            if package in FIPS_INCOMPATIBLE_PACKAGES:
                issues.append(
                    FipsIssue(
                        file_path=file_path,
                        line_number=line_num,
                        severity="error",
                        category="package",
                        message=f"FIPS-incompatible package: {package}",
                        fix_hint=FIPS_INCOMPATIBLE_PACKAGES[package],
                    )
                )
            elif package in FIPS_VERIFY_PACKAGES:
                issues.append(
                    FipsIssue(
                        file_path=file_path,
                        line_number=line_num,
                        severity="info",
                        category="package",
                        message=f"Package may need FIPS verification: {package}",
                        fix_hint=FIPS_VERIFY_PACKAGES[package],
                    )
                )

    except Exception as e:
        issues.append(
            FipsIssue(
                file_path=file_path,
                line_number=0,
                severity="warning",
                category="parse",
                message=f"Error reading requirements file: {e}",
            )
        )

    return issues


def find_python_files(directories: list[Path]) -> Iterator[Path]:
    """Find all Python files in the given directories."""
    for directory in directories:
        if directory.exists():
            yield from directory.rglob("*.py")


def print_issue(issue: FipsIssue, show_hints: bool = False) -> None:
    """Print a FIPS issue with formatting."""
    severity_symbols = {"error": "✗", "warning": "⚠", "info": "i"}
    severity_colors = {"error": "\033[91m", "warning": "\033[93m", "info": "\033[94m"}
    reset = "\033[0m"

    symbol = severity_symbols.get(issue.severity, "?")
    color = severity_colors.get(issue.severity, "")

    location = (
        f"{issue.file_path}:{issue.line_number}"
        if issue.line_number
        else str(issue.file_path)
    )
    print(f"{color}{symbol}{reset} [{issue.severity.upper()}] {location}")
    print(f"  {issue.message}")

    if show_hints and issue.fix_hint:
        print(f"  💡 {issue.fix_hint}")
    print()


def _collect_all_issues(args: argparse.Namespace) -> list[FipsIssue]:
    """Collect all FIPS issues from source and dependency files.

    Args:
        args: Parsed command-line arguments.

    Returns:
        List of all FIPS issues found.
    """
    all_issues: list[FipsIssue] = []

    # Check Python source files
    dirs_to_check = [args.src_dir]
    if args.include_tests:
        dirs_to_check.append(Path("tests"))

    for file_path in find_python_files(dirs_to_check):
        if "__pycache__" in str(file_path):
            continue
        all_issues.extend(check_python_file(file_path))

    # Check dependency files
    all_issues.extend(check_pyproject_toml(Path("pyproject.toml")))
    all_issues.extend(check_requirements_file(Path("requirements.txt")))
    all_issues.extend(check_requirements_file(Path("requirements-dev.txt")))

    return all_issues


def _print_json_output(all_issues: list[FipsIssue]) -> None:
    """Print issues in JSON format.

    Args:
        all_issues: List of all FIPS issues to output.
    """
    import json  # noqa: PLC0415

    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    infos = [i for i in all_issues if i.severity == "info"]

    output = {
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(infos),
        },
        "issues": [
            {
                "file": str(i.file_path),
                "line": i.line_number,
                "severity": i.severity,
                "category": i.category,
                "message": i.message,
                "fix_hint": i.fix_hint,
            }
            for i in all_issues
        ],
    }
    print(json.dumps(output, indent=2))


def _print_text_output(all_issues: list[FipsIssue], show_hints: bool) -> None:
    """Print issues in human-readable text format.

    Args:
        all_issues: List of all FIPS issues to output.
        show_hints: Whether to show fix hints.
    """
    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    infos = [i for i in all_issues if i.severity == "info"]

    print("=" * 60)
    print("FIPS 140-2/140-3 Compatibility Check")
    print("=" * 60)
    print()

    if all_issues:
        # Print errors first, then warnings, then info
        for issue in errors + warnings + infos:
            print_issue(issue, show_hints=show_hints)
    else:
        print("✓ No FIPS compatibility issues found")
        print()

    # Summary
    print("-" * 60)
    print(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info")
    print()

    if errors:
        print("FIPS Compliance: ❌ FAILED")
        print("  Address errors before deploying to FIPS-enabled systems.")
    elif warnings:
        print("FIPS Compliance: ⚠️  NEEDS REVIEW")
        print("  Review warnings for potential FIPS issues.")
    else:
        print("FIPS Compliance: ✅ PASSED")


def _determine_exit_code(all_issues: list[FipsIssue], strict: bool) -> int:
    """Determine exit code based on issues found and strictness.

    Args:
        all_issues: List of all FIPS issues found.
        strict: Whether to treat warnings as errors.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]

    if errors:
        return 1
    if strict and warnings:
        return 1
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for FIPS 140-2/140-3 compatibility issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Check src/ directory
  %(prog)s --strict           # Treat warnings as errors
  %(prog)s --fix-hints        # Show fix suggestions
  %(prog)s --include-tests    # Also check test files
        """,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1 on warnings)",
    )
    parser.add_argument(
        "--fix-hints",
        action="store_true",
        help="Show fix hints for each issue",
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path("src"),
        help="Source directory to check (default: src)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Also check test files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    all_issues = _collect_all_issues(args)

    if args.json:
        _print_json_output(all_issues)
    else:
        _print_text_output(all_issues, args.fix_hints)

    return _determine_exit_code(all_issues, args.strict)


if __name__ == "__main__":
    sys.exit(main())
