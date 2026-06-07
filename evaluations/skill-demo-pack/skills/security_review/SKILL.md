# Security Review Skill

Use this skill when reviewing application code for security risk.

## Method

1. Start with the data flow: identify external inputs, trust boundaries, privileged files, and outgoing responses.
2. Check authentication and authorization before checking style or maintainability.
3. For every finding, include an exploit sketch that a developer can reproduce safely.
4. Distinguish confirmed vulnerabilities from hypotheses.
5. Prioritize fixes by user impact and exploitability.

## Required Report Shape

- Summary
- Findings
- Evidence
- Exploit sketch
- Fix plan
- Regression tests

## Minimum Checks

- SQL injection or unsafe query construction
- Path traversal or arbitrary file access
- Hard-coded secrets
- Missing authorization on privileged routes
- Sensitive file download or data exfiltration
