# Your repository is only part of the secret trail

Keeping an API key out of Git does not tell you where a Claude Code tool result was saved. If a command prints a credential, the output can persist in a session record or an optional memory integration.

In our local setup, a remediation pass recorded 202 value-replacement events in claude-mem and Chroma SQLite stores. These were retained local copies, not 202 unique credentials or evidence of theft.

Project Observatory can inspect selected artifacts for locally known secret values and report findings with the values withheld. The full engine is open source; each user keeps their own private workspace and keys.

[Read the case and what to check before sharing a transcript](https://observatory.sshlg.me/field-notes/).
