# The task finished. The credential copy stayed.

An agent runs a tool, reads the result and moves on. A transcript or memory database may keep the output much longer.

That is one way a credential can leave its intended storage without leaving the machine. It is also why checking only the repository is not enough.

In an earlier local deployment, a remediation pass recorded 66 value-replacement events in claude-mem SQLite and 136 in Chroma SQLite. Total: 202.

I want to be precise about that number. These were replacement events, not unique keys, incidents or vulnerabilities in the applications. The records do not establish remote exfiltration or prove that every copy was removed. The published case study contains the aggregate; project names, credential labels, paths and raw records stay private.

That experience is part of why I built Project Observatory.

## Give the next agent somewhere to look

Observatory collects project state into a local registry and history. You select a project directory; it discovers repositories within that boundary. Git activity, working-tree changes, metrics and findings become available through local dashboards, CLI commands and MCP tools.

Optional integrations extend that view to repository hosts, hosting accounts, domains, analytics and local agent activity. Missing sources should remain visibly unavailable. They should not turn into a green status just because nothing was collected.

Known-value scans compare locally available credential values with supported artifacts. The resulting finding gives the operator a place to act. Revoke or rotate at the provider, inspect retained copies, then scan again. These steps have different effects; deleting a local copy does not revoke the credential.

The complete engine includes optional remediation for supported companion memory stores, with private backups before changes. It is not enabled by the default local pipeline. The tool does not promise to erase every historical backup, embedding or encoded copy.

## Same engine, different private workspaces

The initial public package was a smaller portable implementation. The new release includes the original engine, with state separated from installed source.

Anyone can run the code with their own accounts. Nobody needs my keys or project inventory. Configuration, registry data, credentials and generated dashboards belong to the user's private workspace. The public repository has clean history rather than the history of my operational installation.

This is a local tool. Default secret slots are private files, not a promise of encryption at rest. Backups need protection too.

## Start through your agent

The onboarding prompt asks the agent to check requirements, initialize a separate workspace and run the doctor. Then you choose the project directory and make the first local observation. No provider key is required for that starting point.

Integrations are offered individually. Keys go into a local hidden prompt, protected file or credential manager, never into the chat. Background jobs and paid model actions require an explicit choice.

The same care applies to updates. Contracts have versions; unsupported future formats are refused before normal writes. Upgrades have a preview and private backup. Restore uses a separate home and the matching previous application release. The older portable CLI remains available in its own compatibility mode.

## Part of the harness

Skills stay at the centre of the Skills site. A separate Harness section explains the surrounding system: specialist skills, delivery and verification, Project Observatory for observation, and Asset Foundry, currently in development, for asset workflows.

Observatory also works on its own. Start with one project directory and see whether the first findings help you decide what to do next.

Source and setup: https://observatory.sshlg.me/

Case study and full article: https://observatory.sshlg.me/field-notes/
