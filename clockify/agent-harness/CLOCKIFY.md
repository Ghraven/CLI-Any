# Clockify harness architecture

This harness implements the read/write scope discussed in
[CLI-Anything #317](https://github.com/HKUDS/CLI-Anything/issues/317).
It calls the documented Clockify REST and Reports APIs directly:
[official API reference](https://docs.clockify.me/).

## Backend and data model

Clockify owns workspace, user, project, client, tag, task, user-group and
time-entry records. The harness does not emulate the service or maintain a
shadow database. IDs come from API responses. The selected workspace and
current user ID are cached only for the lifetime of a session.

- `core/api.py`: authenticated Requests session, endpoint configuration,
  finite timeouts, response/error decoding and bounded list pagination.
- `core/session.py`: in-memory workspace and output-mode selection.
- `commands/resources.py`: workspace discovery, project/task operations,
  clients/tags and user-group membership.
- `commands/time.py`: manual entries, timer lifecycle and complete PUT updates.
- `commands/report.py`: summary and detailed Reports API requests.
- `clockify_cli.py`: Click root, JSON error handling, REPL and connection cleanup.
- `utils/command.py`: timezone/date validation, file payloads and common options.
- `utils/repl_skin.py`: unchanged plugin skin.

## API mapping

Core requests use `https://api.clockify.me/api/v1`; reports use
`https://reports.api.clockify.me/v1`. Regional installations configure both
base URLs explicitly. All calls carry `X-Api-Key`.

| Workflow | Method and path after the base URL |
|---|---|
| Current user / workspaces | `GET /user`, `GET /workspaces` |
| Workspace details / members | `GET /workspaces/{w}`, `GET /workspaces/{w}/users` |
| Projects, clients, tags, groups | `GET/POST /workspaces/{w}/{resource}`, `PUT/DELETE .../{id}` |
| Project tasks | `GET/POST /workspaces/{w}/projects/{p}/tasks`, `GET/PUT/DELETE .../{id}` |
| Time entry list | `GET /workspaces/{w}/user/{u}/time-entries` |
| Manual entry / timer start | `POST /workspaces/{w}/time-entries` |
| Entry read / update / delete | `GET/PUT/DELETE /workspaces/{w}/time-entries/{id}` |
| Timer stop | `PATCH /workspaces/{w}/user/{u}/time-entries` |
| Group membership | `POST .../user-groups/{g}/users`, `DELETE .../users/{u}` |
| Summary / detailed reports | `POST /workspaces/{w}/reports/{summary|detailed}` on Reports API |

Core list pagination uses `page` and `page-size` query parameters.
Detailed reports use `detailedFilter.page` and `detailedFilter.pageSize`
in the JSON body. The workspace list is not paginated.

Time entry timestamps have offsets. Reports interpret offset-free dates in
`timeZone`; the harness normalizes input instants to UTC and sets that zone
explicitly. Report grouping is server-side and totals are preserved verbatim.

## Mutation and failure behavior

Writes occur only through explicit commands. PUT updates accept complete API
payload files; they do not read and merge server state. Deletions require
`--yes`. Server permission, archived-project and required-field rules are
reported as API errors. There is no local undo.

The client never retries a mutation or follows a redirect. A timeout can mean
the server completed the operation; callers should inspect remote state before
retrying. Pagination errors return no partial successful result.

The API key is loaded from `CLOCKIFY_API_KEY` and is never written to a
configuration file or command history. Error bodies redact the configured key.
Interactive history follows the standard plugin skin; piped JSON sessions use
neither prompts nor history files.

## Verification

Unit tests use synthetic HTTP responses. Local HTTP subprocess tests exercise
the installed CLI and real Requests transport, clearly separate from live
Clockify tests. Live read and write checks must be selected and configured
explicitly; no backend result is fabricated when credentials are absent.
See `cli_anything/clockify/tests/TEST.md` for commands and recorded evidence.
