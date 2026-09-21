When an agent finishes a task, the repository is only part of what remains.

Tool output can persist in transcripts, memory databases and reports. In an earlier local deployment, our remediation records counted 202 value-replacement events: 66 in claude-mem SQLite and 136 in Chroma SQLite.

These are replacement events, not unique credentials or proof of remote exfiltration. The public account keeps that distinction explicit and excludes project identities, credential labels and raw records.

I built Project Observatory to inspect this surrounding state alongside the projects themselves. It collects repository activity, metrics, findings and history, with local dashboards, CLI and MCP access. Provider integrations and remediation are optional.

The complete engine is now open source. Each user keeps their own configuration, credentials and observations in a private workspace outside the installed code. An agent guides setup without asking for secret values in the conversation. Versioned contracts, upgrade preview and backup/restore support future changes.

For teams experimenting with agent workflows, the useful question is: what evidence will the next person or agent have when they return to this project?

The story, boundaries and setup:
https://observatory.sshlg.me/field-notes/
