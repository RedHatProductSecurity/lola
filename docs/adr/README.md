# Architecture Decision Records

We use ADRs to document significant architectural decisions for the Lola project.
See [use-adrs.md](use-adrs.md) for the full convention, naming rules, and how
to create, update, and deprecate ADRs.

## Quick Start

```bash
make adr-new 0012-topic-name
```

This copies the template to `docs/adr/0012-topic-name.md`. Take the next unused
number; see [use-adrs.md](use-adrs.md) for the naming rule. Fill in the sections
and open a pull request.

## ADR Statuses

| Status | Meaning |
|--------|---------|
| **Proposed** | Under discussion, not yet accepted |
| **Accepted** | Approved and in effect |
| **Deprecated** | No longer relevant |

## Template Changes

If the template needs to change, describe what changed and why here in this file,
apply the change to `template.md`, and open a pull request for Core Maintainer
approval.
