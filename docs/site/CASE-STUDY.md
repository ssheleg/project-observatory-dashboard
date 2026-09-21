# Credential copies in local agent memory

This is a reviewed aggregate from an earlier local deployment, not a benchmark of the public release and not a vendor vulnerability report.

## What was observed

The first recorded remediation pass on 2026-09-14 logged **66 value-replacement events in claude-mem SQLite** and **136 in Chroma SQLite**. The sum is **202 replacement events**. The per-surface totals were checked against the sum of the entries in each corresponding local remediation receipt. No new scan or credential read was performed to prepare this account.

These are replacement events, not unique database cells, distinct credentials, security incidents or people affected. More than one named credential reference can affect the same cell, and several references may refer to one value. We do not claim that either application caused a vulnerability or that any value left the machine. The receipts do not prove that all retained copies were removed or that a provider revoked the credential.

## Before and after

Before inspection, retained memory records contained copies of values intended to remain in credential storage. The local deployment identified those copies and recorded its replacements. A replacement is only part of the response: credential rotation or revocation belongs at the provider; retention and remaining copies still need review.

The full public engine includes known-value scanning and an explicitly enabled companion-memory remediation tool. That tool creates private backups before changing supported stores. The default local pipeline does not enable remediation, rotate credentials or revoke them at a provider. The smaller compatibility CLI retains its read-only exposure checks. Neither workflow proves that all copies, embeddings or historical backups have been erased.

## Provenance and limits

The source is an operator-owned private remediation journal. Only the date, surface names and event totals above were approved for this public aggregate. Raw rows, credential labels, values, file locations, project identities and the private journal are deliberately excluded. Public readers can verify the arithmetic in `case-study.json`, but cannot independently reproduce the private observation from this repository. The claim is an attributed historical observation, not an independently reproducible experiment.

Reviewed 2026-09-21. The interactive website example is separately authored synthetic data and must never be presented as a screenshot or receipt from this deployment.
