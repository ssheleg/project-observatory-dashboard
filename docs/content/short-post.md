# Project Observatory, with your own data

When an agent finishes, its output can stay in transcripts, memory databases and generated reports. Those artifacts deserve the same attention as the repository.

In an earlier local deployment, one remediation pass recorded 202 value-replacement events: 66 in claude-mem SQLite and 136 in Chroma SQLite. These were retained credential copies, not a count of unique keys or evidence of remote exfiltration. The public case study includes the aggregate and its limits; project names, paths and raw records remain private.

Project Observatory turns that problem into a local observation workflow. It discovers repositories in a directory you choose, records Git activity and metrics, tracks findings and history, and exposes the result through a dashboard, CLI and MCP. Optional adapters cover repository hosts, hosting, domains and analytics.

The open-source release includes the complete engine. Every user supplies their own project directory, account access and credentials. Configuration, secret slots, databases and generated reports live in a private workspace outside the installed code.

Setup is guided by your coding agent. Start locally without provider keys, then enable integrations individually. Enter secrets through a local prompt or credential manager, never through chat.

Updates have version checks, a preview, backup and restore. The earlier portable CLI stays available separately for compatibility.

[Read the full story](https://observatory.sshlg.me/field-notes/) or [set up your workspace](https://observatory.sshlg.me/#start).
