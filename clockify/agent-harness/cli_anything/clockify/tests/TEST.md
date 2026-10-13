# Clockify test plan

## Inventory

- `test_core.py`: approximately 60 unit and CLI tests, using synthetic HTTP
  responses to verify request contracts without an account.
- `test_transport.py`: approximately 5 local HTTP transport tests, including
  subprocess JSON output and a complete create/get/delete workflow. These
  validate the harness transport, not the Clockify service.
- `test_full_e2e.py`: installed-command checks plus explicitly selected live
  Clockify tests. Live tests fail when credentials are missing; they do not
  substitute a fake backend.

## Unit plan

- HTTP client: API-key headers, separate core/reports base URLs, encoded IDs,
  timeouts, HTTP failures, malformed responses, rate-limit metadata, redirect
  refusal, and credential redaction.
- Pagination: one page, multiple pages, empty final page, repeated pages, and
  bounded collection without silently returning a partial result.
- Commands: correct methods, paths, query parameters and payloads for
  workspaces, projects, clients, tags, tasks, teams, time entries and reports.
- Validation: timezone-aware timestamps, ordered date ranges, missing workspace,
  invalid JSON files, explicit deletion confirmation, and parser errors.
- Session/REPL: workspace selection survives commands, JSON mode is retained,
  command failures do not exit the loop, and connections close on exit.

## Workflow scenarios

1. Discover workspaces, select one, list projects, create a manual time entry,
   read it, then explicitly delete it. Verify every request and returned ID.
2. Start a timer with project/task/tags, then stop the current user's timer.
   Verify the stop request uses the current user and the same workspace.
3. Fetch detailed and summary reports for a timezone-qualified date range.
   Verify report API routing, grouping, filters, and pagination.
4. Install a built wheel outside the checkout, run the executable and module,
   and verify bundled skill documentation.

## Live verification

Use a disposable workspace. `CLOCKIFY_API_KEY` and `CLOCKIFY_WORKSPACE_ID`
are required. Read-only checks use `pytest -m live -k read`. The write
lifecycle additionally requires `CLOCKIFY_LIVE_WRITES=1`; it creates and
deletes only a uniquely named test time entry. No live request is part of
the default offline validation command, `pytest -m "not live"`.

## Results — 2026-10-13

The initial plan above was written before the tests. The completed suite contains
88 core tests, 5 local HTTP transport tests, 11 installed CLI smoke tests, and
4 real-service tests.

| Environment | Installation and scope | Result |
|---|---|---|
| macOS, Python 3.10.8, pytest 9.1.1 | Editable install; installed executable required | 104 passed, 4 deselected |
| macOS, Python 3.14.6, pytest 9.1.1 | Built wheel installed in a separate environment; tests copied outside the checkout; installed executable required | 104 passed, 4 deselected |

Both runs used `CLI_ANYTHING_FORCE_INSTALLED=1` and explicitly excluded live
tests with `-m "not live"`. The second run imported the package from the Python
3.14 environment's `site-packages`, not the source checkout. Local HTTP tests
bind only to a loopback address and exercise Requests and CLI subprocesses.
They are not evidence of live Clockify interoperability.

Additional checks passed:

- `python -m build --no-isolation`: wheel and source distribution built.
- Wheel includes the README, packaged skill and license; preserves the PEP 420
  namespace; excludes tests. Source distribution includes tests and the SOP.
- Installed executable and `python -m cli_anything.clockify.clockify_cli` both
  report version `0.1.0`.
- Ruff lint and formatting for the new harness, excluding the unchanged skin.
- Root skill validation and the skill creator's `quick_validate.py`.
- Packaged `repl_skin.py` is byte-identical to the plugin copy.
- `git diff --check`.

### Real-service verification not performed

The four `live` tests were not run: no Clockify account credentials were used.
Remote permissions, plan restrictions, service behavior, and the real write
lifecycle remain unverified. Selecting live tests without the documented
credentials fails explicitly; no mock response substitutes for the service.

### Python 3.10 verbose output

Command (from `clockify/agent-harness`):

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/clockify/tests -m "not live" -v --tb=short
```

```text
============================= test session starts ==============================
platform darwin -- Python 3.10.8, pytest-9.1.1, pluggy-1.6.0 -- /private/tmp/clockify-cli-310/bin/python
cachedir: .pytest_cache
rootdir: /Users/sandog/sandog/code/kaiyuan-space/.worktrees/cli-anything-clockify-20261013-b72e4c/clockify/agent-harness
configfile: pyproject.toml
collecting ... collected 108 items / 4 deselected / 104 selected

cli_anything/clockify/tests/test_core.py::test_read_commands[args0-https://api.clockify.me/api/v1/user-payload0] PASSED [  0%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args1-https://api.clockify.me/api/v1/workspaces-payload1] PASSED [  1%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args2-https://api.clockify.me/api/v1/workspaces/ws-payload2] PASSED [  2%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args3-https://api.clockify.me/api/v1/workspaces/ws/projects/p-payload3] PASSED [  3%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args4-https://api.clockify.me/api/v1/workspaces/ws/clients/c-payload4] PASSED [  4%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args5-https://api.clockify.me/api/v1/workspaces/ws/tags/t-payload5] PASSED [  5%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args6-https://api.clockify.me/api/v1/workspaces/ws/projects/p/tasks/t-payload6] PASSED [  6%]
cli_anything/clockify/tests/test_core.py::test_read_commands[args7-https://api.clockify.me/api/v1/workspaces/ws/time-entries/entry-payload7] PASSED [  7%]
cli_anything/clockify/tests/test_core.py::test_resource_lists_have_explicit_pagination[args0-projects] PASSED [  8%]
cli_anything/clockify/tests/test_core.py::test_resource_lists_have_explicit_pagination[args1-clients] PASSED [  9%]
cli_anything/clockify/tests/test_core.py::test_resource_lists_have_explicit_pagination[args2-tags] PASSED [ 10%]
cli_anything/clockify/tests/test_core.py::test_resource_lists_have_explicit_pagination[args3-user-groups] PASSED [ 11%]
cli_anything/clockify/tests/test_core.py::test_resource_lists_have_explicit_pagination[args4-projects/p/tasks] PASSED [ 12%]
cli_anything/clockify/tests/test_core.py::test_resource_lists_have_explicit_pagination[args5-users] PASSED [ 13%]
cli_anything/clockify/tests/test_core.py::test_list_filters_use_api_field_names PASSED [ 14%]
cli_anything/clockify/tests/test_core.py::test_all_pages_and_filters PASSED [ 15%]
cli_anything/clockify/tests/test_core.py::test_all_pages_exact_multiple_ends_with_empty_page PASSED [ 16%]
cli_anything/clockify/tests/test_core.py::test_repeated_page_is_an_error_not_partial_success PASSED [ 17%]
cli_anything/clockify/tests/test_core.py::test_page_limit_is_explicit PASSED [ 18%]
cli_anything/clockify/tests/test_core.py::test_listing_rejects_wrong_response_shape PASSED [ 19%]
cli_anything/clockify/tests/test_core.py::test_named_resource_create[client-clients] PASSED [ 20%]
cli_anything/clockify/tests/test_core.py::test_named_resource_create[tag-tags] PASSED [ 21%]
cli_anything/clockify/tests/test_core.py::test_named_resource_create[team-user-groups] PASSED [ 22%]
cli_anything/clockify/tests/test_core.py::test_create_project PASSED     [ 23%]
cli_anything/clockify/tests/test_core.py::test_task_create_assignees PASSED [ 24%]
cli_anything/clockify/tests/test_core.py::test_resource_updates_forward_explicit_payload[args0-/projects/p] PASSED [ 25%]
cli_anything/clockify/tests/test_core.py::test_resource_updates_forward_explicit_payload[args1-/clients/c] PASSED [ 25%]
cli_anything/clockify/tests/test_core.py::test_resource_updates_forward_explicit_payload[args2-/tags/t] PASSED [ 26%]
cli_anything/clockify/tests/test_core.py::test_resource_updates_forward_explicit_payload[args3-/user-groups/g] PASSED [ 27%]
cli_anything/clockify/tests/test_core.py::test_resource_updates_forward_explicit_payload[args4-/projects/p/tasks/t] PASSED [ 28%]
cli_anything/clockify/tests/test_core.py::test_delete_requires_yes_and_reports_id[args0-/projects/p-p] PASSED [ 29%]
cli_anything/clockify/tests/test_core.py::test_delete_requires_yes_and_reports_id[args1-/clients/c-c] PASSED [ 30%]
cli_anything/clockify/tests/test_core.py::test_delete_requires_yes_and_reports_id[args2-/tags/t-t] PASSED [ 31%]
cli_anything/clockify/tests/test_core.py::test_delete_requires_yes_and_reports_id[args3-/user-groups/g-g] PASSED [ 32%]
cli_anything/clockify/tests/test_core.py::test_delete_requires_yes_and_reports_id[args4-/projects/p/tasks/t-t] PASSED [ 33%]
cli_anything/clockify/tests/test_core.py::test_delete_requires_yes_and_reports_id[args5-/time-entries/e-e] PASSED [ 34%]
cli_anything/clockify/tests/test_core.py::test_team_membership PASSED    [ 35%]
cli_anything/clockify/tests/test_core.py::test_manual_time_entry PASSED  [ 36%]
cli_anything/clockify/tests/test_core.py::test_start_timer_defaults_to_now_and_has_no_end PASSED [ 37%]
cli_anything/clockify/tests/test_core.py::test_stop_timer_uses_authenticated_user PASSED [ 38%]
cli_anything/clockify/tests/test_core.py::test_stop_another_user_does_not_query_current_user PASSED [ 39%]
cli_anything/clockify/tests/test_core.py::test_time_list_current_user_and_filters PASSED [ 40%]
cli_anything/clockify/tests/test_core.py::test_time_update_is_full_put PASSED [ 41%]
cli_anything/clockify/tests/test_core.py::test_reports_have_correct_timezone_filters_and_host[summary] PASSED [ 42%]
cli_anything/clockify/tests/test_core.py::test_reports_have_correct_timezone_filters_and_host[detailed] PASSED [ 43%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args0-timezone] PASSED [ 44%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args1-precede] PASSED [ 45%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args2-requires --project] PASSED [ 46%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args3-2 to 250] PASSED [ 47%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args4-RGB] PASSED [ 48%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args5-name] PASSED [ 49%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args6-range] PASSED [ 50%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args7-range] PASSED [ 50%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args8-range] PASSED [ 51%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args9-Missing option] PASSED [ 52%]
cli_anything/clockify/tests/test_core.py::test_invalid_arguments_never_send_requests[args10-No such command] PASSED [ 53%]
cli_anything/clockify/tests/test_core.py::test_invalid_time_update_file[{] PASSED [ 54%]
cli_anything/clockify/tests/test_core.py::test_invalid_time_update_file[[]] PASSED [ 55%]
cli_anything/clockify/tests/test_core.py::test_invalid_time_update_file[{"end": "2026-10-01T00:00:00Z"}] PASSED [ 56%]
cli_anything/clockify/tests/test_core.py::test_invalid_time_update_file[{"start": 123}] PASSED [ 57%]
cli_anything/clockify/tests/test_core.py::test_timestamp_normalizes_offsets[2026-01-02T00:30:00+02:00-2026-01-01T22:30:00.000Z] PASSED [ 58%]
cli_anything/clockify/tests/test_core.py::test_timestamp_normalizes_offsets[2026-01-01T23:30:00-02:00-2026-01-02T01:30:00.000Z] PASSED [ 59%]
cli_anything/clockify/tests/test_core.py::test_timestamp_normalizes_offsets[2026-01-01T09:00:00.125Z-2026-01-01T09:00:00.125Z] PASSED [ 60%]
cli_anything/clockify/tests/test_core.py::test_missing_workspace_prevents_even_user_lookup PASSED [ 61%]
cli_anything/clockify/tests/test_core.py::test_missing_key_has_json_error PASSED [ 62%]
cli_anything/clockify/tests/test_core.py::test_http_errors_are_structured_and_never_retried[400] PASSED [ 63%]
cli_anything/clockify/tests/test_core.py::test_http_errors_are_structured_and_never_retried[401] PASSED [ 64%]
cli_anything/clockify/tests/test_core.py::test_http_errors_are_structured_and_never_retried[403] PASSED [ 65%]
cli_anything/clockify/tests/test_core.py::test_http_errors_are_structured_and_never_retried[404] PASSED [ 66%]
cli_anything/clockify/tests/test_core.py::test_http_errors_are_structured_and_never_retried[429] PASSED [ 67%]
cli_anything/clockify/tests/test_core.py::test_http_errors_are_structured_and_never_retried[500] PASSED [ 68%]
cli_anything/clockify/tests/test_core.py::test_transport_errors_are_structured[Timeout] PASSED [ 69%]
cli_anything/clockify/tests/test_core.py::test_transport_errors_are_structured[ConnectionError] PASSED [ 70%]
cli_anything/clockify/tests/test_core.py::test_invalid_json_success_is_not_hidden PASSED [ 71%]
cli_anything/clockify/tests/test_core.py::test_html_error_does_not_dump_response_body PASSED [ 72%]
cli_anything/clockify/tests/test_core.py::test_redirect_does_not_forward_credentials PASSED [ 73%]
cli_anything/clockify/tests/test_core.py::test_configured_hosts_and_timeout PASSED [ 74%]
cli_anything/clockify/tests/test_core.py::test_invalid_base_url_rejected[http://api.clockify.me/api/v1] PASSED [ 75%]
cli_anything/clockify/tests/test_core.py::test_invalid_base_url_rejected[https://user:pass@example.test/api] PASSED [ 75%]
cli_anything/clockify/tests/test_core.py::test_invalid_base_url_rejected[file:///tmp/api] PASSED [ 76%]
cli_anything/clockify/tests/test_core.py::test_invalid_base_url_rejected[https://example.test/api?key=secret] PASSED [ 77%]
cli_anything/clockify/tests/test_core.py::test_resource_ids_are_encoded PASSED [ 78%]
cli_anything/clockify/tests/test_core.py::test_timeout_must_be_finite[nan] PASSED [ 79%]
cli_anything/clockify/tests/test_core.py::test_timeout_must_be_finite[inf] PASSED [ 80%]
cli_anything/clockify/tests/test_core.py::test_malformed_base_url_has_json_error PASSED [ 81%]
cli_anything/clockify/tests/test_core.py::test_repl_cannot_nest_via_global_options PASSED [ 82%]
cli_anything/clockify/tests/test_core.py::test_repl_preserves_workspace_json_and_user_cache PASSED [ 83%]
cli_anything/clockify/tests/test_core.py::test_repl_handles_quotes_and_keeps_running PASSED [ 84%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args0] PASSED [ 85%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args1] PASSED [ 86%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args2] PASSED [ 87%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args3] PASSED [ 88%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args4] PASSED [ 89%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args5] PASSED [ 90%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args6] PASSED [ 91%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args7] PASSED [ 92%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_command_help[args8] PASSED [ 93%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_version_and_bundled_skill PASSED [ 94%]
cli_anything/clockify/tests/test_full_e2e.py::test_installed_missing_credentials_is_json PASSED [ 95%]
cli_anything/clockify/tests/test_transport.py::test_installed_cli_create_get_delete_over_http PASSED [ 96%]
cli_anything/clockify/tests/test_transport.py::test_installed_repl_timer_workflow PASSED [ 97%]
cli_anything/clockify/tests/test_transport.py::test_installed_cli_pagination_over_http PASSED [ 98%]
cli_anything/clockify/tests/test_transport.py::test_installed_cli_report_separate_base_url PASSED [ 99%]
cli_anything/clockify/tests/test_transport.py::test_installed_cli_json_http_error PASSED [100%]

====================== 104 passed, 4 deselected in 6.40s =======================
```
