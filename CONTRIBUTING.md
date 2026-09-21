# Contributing

Start with [scope and acceptance criteria](docs/MIGRATION.md) and the [security boundary](SECURITY.md). This is a portable local observer: additions must retain explicit scope, meaningful degraded results and value-free output.

Run `python -m unittest discover -s tests -v`. Tests must use temporary roots, synthetic values and local fixtures. Do not make tests depend on an agent installation, real provider credentials, personal projects or live network access. Add a failure-case test for a new security boundary; do not count source-string assertions as runtime evidence.

The public source must remain independent of private operational history. Do not submit generated dashboards, inventories, provider exports, local state, customer references or screenshots containing real data. New adapters need least-privilege configuration, timeouts, pagination, explicit opt-in and fixture-backed error behavior.

Update user scenarios and onboarding in the same change as behavior. Clearly separate shipped functionality from migration plans. Reproducible evidence belongs with the claim: a test, a command and result, or a source reference. Pull requests should state what changed, why, what was tested and any remaining limitations.
