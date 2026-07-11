# Security Policy

## Reporting a Vulnerability

The Antigravity-K project takes security bugs seriously. We appreciate your
efforts to responsibly disclose your findings and will make every effort to
acknowledge your contributions.

### How to Report

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities privately using one of these methods:

1. **GitHub Security Advisories** (preferred): Go to the
   [Security tab](../../security/advisories/new) of this repository and select
   "Report a vulnerability." This uses GitHub's private vulnerability
   reporting.
2. **Email**: Send a description of the issue and reproduction steps to the
   maintainer. (Replace with a dedicated security email if one exists.)

### What to Include

To help us triage and fix the issue quickly, please include:

- A description of the vulnerability and its impact.
- The exact version(s) affected (commit hash or tag).
- Step-by-step reproduction instructions or a proof-of-concept.
- Any suggested mitigations or fixes.

### Response Timeline

| Step | Target |
|---|---|
| Acknowledgment of receipt | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix or mitigation | Within 30 days (severity-dependent) |
| Public disclosure (if applicable) | After a fix is released, coordinated with you |

## Scope

This policy covers the Antigravity-K codebase and its official Docker images.
Issues in third-party dependencies should be reported upstream and via the
relevant package tracker, but we welcome being notified so we can update
quickly.

## Supported Versions

Only the latest release line (`main` branch) receives security updates.

| Version | Supported |
|---|---|
| latest `main` | ✅ |
| older releases | ❌ |

## Security Measures

The project employs the following security practices:

- **Dependency scanning** (`pip-audit`) and **SAST** (`bandit`) run in CI on
  every push and pull request.
- **Container image scanning** (Trivy) scans the production Docker image for
  known OS and library vulnerabilities.
- **SBOM** (Software Bill of Materials) is generated for each build.
- **Dependabot** opens pull requests for outdated or vulnerable dependencies.
- **Secret scanning** checks for accidentally committed credentials.

## Dependency Policy

- All dependencies must have an upper-bound version constraint or be reviewed
  before merge (new dependencies are flagged in CI).
- Security advisories on dependencies are addressed with priority based on
  severity.
