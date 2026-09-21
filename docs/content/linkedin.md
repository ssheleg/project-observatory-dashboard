Your API key can stay out of Git and still end up in your agent's memory.

When reviewing a Claude Code workflow, the repository is only part of the picture. A command can print a credential into a tool result. Session history can retain it. An optional memory integration can carry information from that result into a separate store.

The task finishes. The application works. The copied key may still be valid.

In our local setup, a remediation pass recorded 66 value-replacement events in claude-mem SQLite and 136 in Chroma SQLite: 202 events in total.

These were retained local credential copies. The count is not a count of unique keys, and the evidence does not establish theft or a vulnerability in those products.

It changed the question I wanted to answer: where else did a credential go after a tool used it?

I built Project Observatory to help inspect that surrounding state. It checks selected artifacts for locally known secret values and records findings without repeating the values. The full engine is open source, with private projects, credentials and observations owned by each installation.

Before sharing an agent transcript or a support bundle, inspect its contents. If a valid key appears somewhere unintended, revocation and removal are separate tasks.

The full write-up covers the copy paths, our evidence and a practical starting point:
https://observatory.sshlg.me/field-notes/
