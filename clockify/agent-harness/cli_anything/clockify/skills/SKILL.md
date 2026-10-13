---
name: cli-anything-clockify
description: Track time, manage Clockify projects and user groups, and query summary or detailed reports through the cli-anything-clockify command.
---

# Clockify CLI

Use `cli-anything-clockify` for Clockify workflows. It requires Python 3.10+,
an account with API access, and `CLOCKIFY_API_KEY` from profile settings.
Install from the repository's `clockify/agent-harness` directory with
`pip install -e .`, or use the CLI-Hub Clockify entry.

Discover IDs through `--json workspace list`, `project list`,
`workspace users`, `client list`, `tag list` and `team list`.
Select a workspace with `--workspace ID` or `CLOCKIFY_WORKSPACE_ID`.
Global options, including `--json`, precede the command group.

## Workflows

```bash
cli-anything-clockify --json --workspace WORKSPACE_ID time start \
  --project PROJECT_ID --description "Review" --billable
cli-anything-clockify --json --workspace WORKSPACE_ID time stop
cli-anything-clockify --json --workspace WORKSPACE_ID time create \
  --start 2026-10-01T09:00:00+08:00 --end 2026-10-01T10:00:00+08:00 \
  --description "Planning"
cli-anything-clockify --json --workspace WORKSPACE_ID report summary \
  --start 2026-10-01T00:00:00Z --end 2026-10-08T00:00:00Z --group USER
```

- `time`: list/get/create/start/stop/update/delete. Listing and stopping default
  to the authenticated user; use `--user` only for an intended user.
- `project`, `client`, `tag`: list/get/create/update/delete.
- `task`: list/get/create/update/delete, with a project ID argument.
- `team`: list/create/update/delete/add-member/remove-member. These are user
  groups, not invitations to join the workspace.
- `report`: summary and detailed; repeated user/project/client/tag filters.
- `whoami` and `workspace`: account/workspace inspection and REPL selection.

Use `COMMAND --help` for exact arguments. Execute mutations only for the
user's requested objects and scope. Deletion and member removal require
`--yes`; there is no undo. Update commands send a **complete PUT request**
from `--data FILE`, not a partial merge. Include the fields that must remain.
Time updates require `start`; custom fields on new entries use a JSON array
through `--custom-fields FILE`.

## Operational details

Timestamps require a timezone. Both APIs receive the same absolute interval:
the harness normalizes to UTC and explicitly sets the Reports API timezone.
Use `--all` for complete resource lists; bounded pagination fails rather than
silently truncating. Detailed reports return one page and server totals;
request subsequent pages with `--page` and do not sum repeated totals.

In `--json` mode, API and subcommand errors emit an `error` object and a
nonzero status. Rate limits can include `retry_after`. Writes are never
automatically retried. After a timeout, inspect the remote state before
repeating a write.

No-argument startup enters the REPL. `workspace use ID` changes only that
session; it does not persist across processes. Piped `--json` sessions emit
one result per command, without banners or prompts.

Regional/custom deployments set both `CLOCKIFY_API_URL` and
`CLOCKIFY_REPORTS_URL` to their full API base URLs. Follow
[Clockify's API reference](https://docs.clockify.me/) for deployment addresses,
complete update schemas, permissions and plan restrictions.
