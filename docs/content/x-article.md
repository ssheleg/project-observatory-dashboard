# Claude Code finished. Your API key may still be in the logs

You keep `.env` out of Git. You avoid pasting credentials into chat. Before publishing a repository, you check for secrets.

But if a command run during a Claude Code session prints a key, where does that output go?

It can become part of the session record. A memory integration can retain information from the tool result. Closing the terminal does not tell you whether those copies are gone. Your application can keep working while a valid credential sits somewhere you never thought to inspect.

That possibility became concrete in our local setup. An earlier remediation pass recorded **202 value-replacement events in memory stores**: 66 in claude-mem SQLite and 136 in Chroma SQLite. We had credential copies outside the storage intended for them.

Those are replacement events, not 202 different keys or confirmed breaches. Our records establish local retention; they do not establish that an attacker obtained the values.

## A clean repository leaves part of the question unanswered

Consider a debugging task. A tool reads configuration or runs a diagnostic command. Its output includes a credential. The output becomes available to the agent, and an installed memory integration processes it.

This is an illustrative route, not a reconstruction of every copy we found. Whether a value is retained depends on what the tool emitted, the permissions and the integrations in that installation.

The mechanisms are documented. Claude Code's [hook reference](https://code.claude.com/docs/en/hooks#common-input-fields) exposes a session transcript path; its [PostToolUse hook](https://code.claude.com/docs/en/hooks#posttooluse) receives tool inputs and responses. The separate claude-mem project documents a [hook that captures tool observations](https://docs.claude-mem.ai/architecture/hooks#stage-3-posttooluse) for memory processing.

**claude-mem is an optional integration, not Claude Code's built-in memory.** Chroma is a separate storage component. Mentioning them identifies where our local copies were found; it does not establish a vulnerability in either product.

A repository scan only covers what it scans. Session records, memory stores, exported reports and their backups can sit outside that scope. Keeping a secret out of Git is useful, but it does not account for every later copy.

## What we found, and what we cannot claim

On 14 September 2026, our local remediation journal recorded:

- **66 value-replacement events in claude-mem SQLite**
- **136 value-replacement events in Chroma SQLite**

Several references can refer to one credential, and a cell can be affected more than once. The total cannot be converted into a count of unique keys, incidents or affected users.

The [case study](https://github.com/ssheleg/project-observatory-open-source/blob/main/docs/site/CASE-STUDY.md) publishes the aggregate and its limits. Project names, values, credential labels and raw records remain private. Readers can verify the arithmetic, but cannot reproduce our private observation from the public repository.

We also cannot infer when every copy was created, who could access it, whether it left the machine, or whether every copy was removed. This is an account of retained local credentials, not an audit of model-provider data handling.

## Before you share that transcript

A transcript can look like harmless debugging history. If it contains a valid key, sharing it also shares whatever access that key grants. The same concern applies when a local memory database is copied into a backup or support bundle.

Start with the artifacts you are about to share and the tools configured to retain your agent's work. Check selected transcripts, tool-output logs and memory stores locally. Keep the review output redacted: the useful result is the location and credential reference, not the value pasted into another conversation.

If you find a valid credential in an unintended location, revoke or rotate it at the provider and review the access it had. Removing the copy does not invalidate the key. Revoking the key does not erase the copy. Cleanup and access control need separate checks.

Avoid asking an agent to print your secrets so it can search for them. That can create another copy while you investigate the first.

## Why I built Project Observatory

I wanted a way to inspect this surrounding state without turning every investigation into another transcript full of sensitive output.

Project Observatory can compare locally known secret values against supported artifacts you explicitly select. It records findings with the value withheld. Its optional companion-memory remediation creates private backups before changing supported stores and requires explicit enablement. Those backups are sensitive too.

This is known-value scanning. It cannot promise to find every unknown secret, encoded copy, embedding or historical backup. The first local workflow does not automatically rotate credentials or erase memory stores.

The open-source release includes the full engine. The code is shared; your project inventory, accounts, credentials and observations stay in your own private workspace. It also tracks project activity and findings so an agent can pick up work with context about what changed.

The [setup guide](https://observatory.sshlg.me/#start) gives you a prompt for your coding agent. Start with a private workspace and a directory you understand. Add integrations individually, and enter keys locally rather than in chat.

Before you export another Claude Code session, check what it contains. A key does not need to appear in a commit to end up somewhere you did not intend.

Originally published: https://observatory.sshlg.me/field-notes/
