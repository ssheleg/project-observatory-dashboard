# Deployments: accounts, environments and what runs where

Status: design for 0.4 (PB-004). Slices PB-004a (accounts), PB-004b (environments) and PB-004c (bindings) shipped in 0.3.3, 0.3.5 and 0.3.6. Other released parts: `deployed_commit` on Heroku apps (0.3.1), account-qualified
Cloudflare zone ids (0.3.1), and a `rule` on every derived edge (0.3.1). This document is the contract that code
comments point to. Project and repository ids come from [IDENTITY.md](IDENTITY.md).

## The problem

The registry knows projects, repositories, Heroku apps, Cloudflare zones, environment files and credentials. It can't
yet answer the questions an operator asks about a running system:

| Question | Why today's registry can't answer it |
|---|---|
| Which account does this app, zone or key live in? | Heroku apps carry a `team` string, zones an `account` id, credentials nothing; none is an entity other rows can point at. |
| Is this the production of project A or of project B? | `deployed_to` links a project to an app. Nothing says which environment that app serves, so two projects' production apps look alike. |
| Is a key used when building, or when running? | `credential_used_by` links a credential to a project. It doesn't say where the credential is bound (a runtime config var, a CI secret, a local file). |
| Two keys have the same name in different accounts: are they the same key? | A credential is named by its slot, and nothing says which account issued it. |
| What commit is running? | Answered in 0.3.1, and only from a release that states a commit (`deployed_commit`); a branch is never shown as a commit. |

## The contract

1. **An environment is explicit or unknown, never guessed.** The evidence, in precedence order:
   - an override in `environments.json`;
   - a provider's own statement, such as a pipeline stage;
   - the environment of the vault slot that holds a credential (`prod`, `stage`, `local`);
   - the suffix of an environment file (`.env.production`, `.env.local`).

   An app name that contains `prod` or `staging` is a name, not evidence. With no evidence, the environment is
   `unassigned`, and the page says so.
2. **Environments are scoped by project.** An environment id is `environment:<project id>/<name>`. The production of
   project A and the production of project B are different ids, even when the provider, the account and the variable
   names are identical.
3. **Accounts are entities.** An account id is `account:<provider>/<provider's account id>`; its label is display
   only. Every provider resource (a Heroku app, a zone, an issued credential) that its provider attributes to an
   account gets an `in_account` edge. A resource whose account the provider did not state has no such edge. It is
   never attached to the only account known.
4. **A deployment is a provider resource that serves an environment.** The resource keeps its existing id
   (`heroku:<app>`, `zone:<name>[@<account>]`). A `serves` edge links it to an environment, and the edge's `rule`
   names the evidence from rule 1.
5. **A credential binding says where the value is read.** Each `credential_used_by` edge gains a `binding`:
   - `run`: a runtime config var of a deployment;
   - `build`: a CI or build secret;
   - `local`: a file or slot on this machine;
   - `unknown`: none of these is known.

   It also gains `environment` when rule 1 gives one. One credential used at build and at run time has two edges.
6. **Same name is not same key.** A credential is identified by its slot. Two slots in different accounts or
   environments are different credentials, even with the same variable name. That two of them hold the same value
   shows only in their salted fingerprints, which are compared within one fingerprint namespace.
7. **Every derived edge names its rule** (0.3.1), and `validate` refuses one without it. That applies to `in_account`,
   `serves` and the new fields on `credential_used_by` as well.

## Registry shape

New file `registry/environments.json` (schema_version 1):

```json
{
  "schema_version": 1,
  "environments": [
    {"id": "environment:project:example-app/production", "project": "project:example-app",
     "name": "production", "evidence": ["vault-slot"], "deployments": ["heroku:example-app"]}
  ],
  "accounts": [
    {"id": "account:heroku/team-id", "provider": "heroku", "label": "example-team", "resources": 12}
  ],
  "unassigned": [{"deployment": "heroku:example-worker", "why": "no pipeline stage, no slot, no override"}],
  "degraded": []
}
```

New relation types in `relations.json`:

- `in_account`: resource → account;
- `serves`: deployment → environment.

The `credential_used_by` edge gains `binding` and, when known, `environment`. Existing ids don't change.

## Slices

| Slice | Delivers | Tests that define done |
|---|---|---|
| PB-004a accounts | `account:*` entities and `in_account` edges for Heroku apps (team, or the personal account) and Cloudflare zones. | Two apps in two teams point at two accounts. A zone without an account id gets no edge. The account label can change without changing the id. |
| PB-004b environments | `environments.json` and `serves` edges from rule 1's evidence; the `environments.json` override; `unassigned` listed. | Two projects' production apps give two environment ids. An app named `*-prod` with no evidence is `unassigned`. An override wins and is named as the rule. |
| PB-004c bindings (0.3.6; `run` is matched by salted fingerprint between a production config var and a vault slot; `build` waits for a CI-secrets scan) | `binding` and `environment` on `credential_used_by`. | A Heroku config var gives `run`. A vault slot `local` gives `local`. The same slot used in two places gives two edges. With no evidence the binding is `unknown`, never `run`. |
| PB-004d pages | The dashboard groups each project's deployments by environment and shows account and binding. | A project with production and staging shows two groups. `unassigned` is visible, not hidden. |

A slice ships only with its tests, a COMPATIBILITY entry and a CHANGELOG entry.

## Out of scope

- Reading config var **values** to infer an environment (`APP_ENV=production`). Values are credentials' neighbours,
  and the engine reads only names and salted fingerprints.
- Providers the engine doesn't scan yet. They join by emitting accounts and deployments in this shape.
- Heroku pipelines. They are the best provider statement of an environment, but the scanner doesn't read them yet.
  Adding them is a scanner change inside PB-004b.
