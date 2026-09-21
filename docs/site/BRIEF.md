# Observatory public website

Objective: help a developer understand the complete Project Observatory, inspect a synthetic exposure workflow, and give an agent the installation/onboarding task.

Scope: `site/` is a static marketing artifact. It never reads local runtime state, credentials, project registries or transcripts. Deploy only this directory. No analytics, third-party scripts, remote fonts or browser access to the local tool.

## Scenarios, before implementation

- SITE-01: First-time builder opens `/`, learns that the product observes projects inside an explicitly configured directory locally, and reaches agent onboarding. Success: purpose and CTA visible in the first desktop viewport; HTML remains useful without JS.
- SITE-02: Maintainer reads before/after credential handling and switches a synthetic example from untracked exposure to a finding and response. Example is labelled synthetic in each state; no tool vendor is blamed and no real incident count is claimed.
- SITE-03: Developer reads the supported capabilities and release boundary before adopting. The full engine includes adapters, MCP and optional scheduling; integrations and background work are disabled until selected. Legacy portable mode is separately labelled.
- SITE-04: Builder copies the agent prompt. Clipboard denial keeps the selectable prompt visible and gives a useful message. The agent never asks for secret values in chat.
- SITE-05: Keyboard/mobile reader reaches navigation, examples and setup without overflow or hidden content. Native HTML is the baseline; animations do not carry information.

Status: approved for autonomous implementation by the operator's explicit request, 2026-09-21. Product outcomes remain unobserved.

## Design direction

New public developer-tool surface. Field-notes pack from sheleg-design, token file copied verbatim, attribution in THIRD_PARTY.md. Quiet paper, forest dawn hero, rust annotations and source labels. System-font fallback is intentional to avoid remote assets; font-specific craft is not claimed.

Variance 6: numbered editorial sections and an annotated sample report. Motion 1: no entrance animation; optional example toggles only. Density 4: one argument per section, readable text column plus a bounded instrument example. Existing family site keeps workbench; this site has its own product identity.

Locked: truthful capability scope, synthetic data, existing harness vocabulary, no data collection. Open: composition and evidence presentation. Compared the dawn and paper-led variants at 1440×900 with identical content. Selected dawn: it separates the opening proposition from the evidence sections, while the paper variant made the first screen read like another documentation section. Both kept purpose and CTA visible. Rubric: purpose/CTA visible at 1440×900, first paragraph legible, sample evidence clearly distinguished from production, no document overflow at 390px. One critique-and-correction pass, then only functional defects justify further changes.

## Brand

Peer-builder voice inherited from the family. Name the mechanism and boundary. Use “Project Observatory”, “ssheleg harness”, “full engine”, “private workspace”, “finding”, “known-value scan”. Never say all leaks, secure by default, enterprise-ready or a guarantee that every live integration was exercised. Historical incident counts are not public facts. A separately reviewed aggregate of value-replacement events is documented in CASE-STUDY.md, with explicit unit and private-source limits. Real instrument names describe file formats/surfaces only when explicitly supported.

## Verification

Run `python3 docs/site/check.py` on the exact static tree; browser-check desktop, mobile, toggle and clipboard fallback. Deploy `site/` only after independent source privacy review. Record actual results and exact revision in the release handoff. All examples are authored synthetic fixtures, not screenshots of a real installation.

- SITE-06: Reader follows Field notes, sees the historical aggregate with its units and limits, then reaches onboarding. The article and cover contain no private project identifiers.
- SITE-07: Reader reaches Harness from Skills or Observatory and understands Skills, observation and in-development asset creation as separate components.

The full-engine article follows the same paper/forest tokens and system fonts. The author-provided request authorizes the update; brand voice is still recorded as an inferred draft, not a separately approved brand pack.

## Returning visitor after deployment

A visitor with the previous CSS/JS in browser cache must receive the assets matching
the new HTML. Local stylesheet/script URLs carry their content digest. The static
gate rejects missing or stale digests; verification reuses a previously visited
production browser and checks responsive landing/article layout after deployment.

- SITE-08: A reader arriving from a credential-risk post gets the same concrete
  question in the article headline, sees local-retention evidence with its limits,
  and reaches a redacted inspection/response path. Claude Code, claude-mem and
  Chroma remain distinct; no breach or universal exposure is asserted.
