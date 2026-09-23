# Identity: how projects and repositories keep their ids

Status: implemented in 0.3.0 (`observatory/engine/identity_map.py`, resolved in
`collectors/emit_registry.py`, read by `identity.project_id`). This document is the contract that
code comments point to.

## The problem

Ids are derived from names that change:

| Entity | Id today | Derived from | Changes when |
|---|---|---|---|
| project anchored by a wiki folder | `project:<slug(folder)>` | the wiki folder name | the folder is renamed |
| project anchored by an organisation | `project:<slug(owner)>` | the GitHub owner | the repositories move to another owner |
| project anchored by one repository | `project:<slug(owner-name)>` | the repository's owner/name | the repository is renamed or transferred |
| local project (no remote) | `project:local-<folder>` | the folder name | the folder is renamed |
| repository | `repository:<owner/name>` | owner/name | rename or transfer |

Nothing records which old id became which new one, except the single computed case of a local
folder that gains a remote or a wiki note (`identity.former_ids`). Events, ledger rows, weekly
rollups, metrics and curated files keep the old id, so a rename splits a project's history in two
and orphans its curation. `identity_overrides.json` can pin an id by hand. It is a flat
key-to-slug map, and nobody remembers to edit it before renaming.

## The contract

1. **An id is minted once and never reused.** The first time a project is seen, it gets
   `project:<slug(key)>`, or a numeric suffix if that id was ever used before.
2. **A rename keeps the id.** A project whose merge key changed keeps the id recorded for it when
   exactly one known project shares a *strong anchor* with it:
   - a repository it is implemented by (`owner/name`, or a former `owner/name` of that repository);
   - the root commit of a local Git history with no remote;
   - the absolute path of a local checkout.

   A wiki folder name, an organisation name or a local folder name alone is a *weak anchor*. It
   identifies the key, not a rename.
3. **Ambiguity is never resolved by guessing.** If a project shares strong anchors with two
   recorded projects, or two current projects claim one recorded id, a new id is minted and an
   `identity.ambiguous` finding names the candidates. The operator decides with
   `identity_overrides.json`, which always wins.
4. **A project that disappears is retired, not deleted.** Its id is marked retired with the date it
   was last seen. It is never minted again, and readers can still show its history.
5. **Repositories remember former names.** A transfer or rename the merge step followed
   (`transfers_followed`) is recorded as a former `owner/name` of the new repository id.
6. **History follows the id through readers, not rewrites.** Stored rows keep the id they were
   written with. Every reader that already widens queries with `identity.ids_for` also widens them
   with the recorded aliases, so a renamed project shows one timeline, one rollup and its notes.
   Stored data is not rewritten in place: an append-only store stays auditable.

## The map

`registry/identity.json`, written by the emit step and committed with the rest of the registry:

```json
{
  "schema_version": 1,
  "projects": {
    "project:example-app": {
      "minted_on": "2026-09-23",
      "keys": ["example-app", "old-example-app"],
      "anchors": {"repositories": ["example-org/example-app"], "root_commits": [], "checkouts": ["/srv/projects/example-app"]},
      "last_seen_on": "2026-09-30",
      "retired_on": null
    }
  },
  "repositories": {
    "repository:example-org/example-app": {"former": ["example-org/example-app-old"]}
  }
}
```

`keys` are aliases: every merge key that ever resolved to this id. `anchors` hold only strong
evidence and are unions over time. Names never appear as anchors.

## Resolution, per emit run

For each project in the merged model:

1. `identity_overrides.json` pins the id when it names the key.
2. Otherwise, if the map already lists the key, that id is used.
3. Otherwise, the project's strong anchors are compared with every non-retired entry. Exactly one
   match means the id is reused, the key is appended and a `renamed` delta is recorded. Two or more
   matches produce a new id and an `identity.ambiguous` finding.
4. Otherwise, a new id is minted.

Resolution runs in two passes, so the order of keys cannot decide a match: overrides and keys the map
already knows claim their ids first, and only then are new keys compared by anchors against the
recorded projects nobody has claimed. If two current projects would take one id (for example an
override pointing at an id another project holds), the first in key order keeps it, the other gets
a new id, and both cases produce an `identity.ambiguous` finding. An entry no project resolved to gets `retired_on`, unless the run was degraded
for the source that anchors it (a partial scan must not retire anything).

`merge.py` also asks `identity.project_id` for a key while matching domain claims. For a project
renamed in this very run it still sees the name-derived id; from the next run the map knows the key.
The emitted registry is correct in the same run.

## Migration

The first run with the map seeds it from the current registry. Every existing id and key is
recorded as is, so no id changes on upgrade. `identity_overrides.json` keeps working and still takes
precedence. Existing `former_ids` (local folder to published) remain an additional alias source.

## Out of scope for this slice

- **Checkouts as entities** (`checkout:<repository>/<folder>`): PB-003b.
- **Components**: several products in one repository, sub-directories of a monorepo. PB-003c; the
  product model stays N projects to 1 product until then.
- **Rewriting stored history**: not planned.

## Tests that define done

- Renaming a wiki folder keeps the project id, the timeline shows both periods, and curation keyed
  by the id still applies.
- A repository transfer keeps the id of a project anchored by that repository, and the repository
  records its former name.
- Renaming a local Git folder without a remote keeps the id through its root commit. Renaming a
  local folder with no Git history mints a new id. This limit is documented, not guessed around.
- Two projects sharing one repository anchor with one recorded id produce `identity.ambiguous`, and
  both get new ids.
- A partial scan retires nothing. A project absent from a complete scan is retired, and its id is
  never minted again.
- The first run on an existing workspace changes no id.
