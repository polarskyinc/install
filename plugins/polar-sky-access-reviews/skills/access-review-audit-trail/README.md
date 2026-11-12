# access-review-audit-trail

Shows the Polar Sky audit trail for a date range from the controls MCP (`get_access_review_audit_trail`): a Markdown table in the chat and `audit-trail.csv`. `SKILL.md` is what Claude follows; this page is for people working on the skill.

## Layout

| Path | What it holds |
|---|---|
| `SKILL.md` | The steps Claude follows |
| `scripts/render_audit_trail.py` | Checks the saved pages and writes `audit-trail.md` and `audit-trail.csv` (Python 3 standard library, no network, no clock) |
| `tests/` | Fixture, golden files and tests |

The script copies the few helpers it shares with the access review report skill (time parsing, CSV escaping) so each skill folder stands alone.

## Data

A folder with `responses/*.json`, read in file name order, or one JSON file `{"responses": [...]}` (the test fixture `tests/fixtures/northwind.json`). Each response is one tool call, copied unchanged:

```json
{"tool": "get_access_review_audit_trail", "arguments": {"from": "2026-09-01", "to": "2026-09-30"}, "response": {…}}
```

Responses of other tools are ignored. The render stops, naming what is missing, when:

- a page chain (one `from`, `to` and `control_id`) has no first page, or a `next_cursor` has no response with that `cursor` in its `arguments`;
- the saved ranges leave part of `--from` to `--to` out, reach outside it, or are for another control than `--control-id`;
- a call was refused and the same page was not fetched again.

## CSV columns

| Column | From |
|---|---|
| `when` | `at` |
| `control`, `control_id`, `folders` | `control`, `control_id`, `folders` |
| `what_changed` | `change` |
| `details` | `step` where the tool words one; otherwise events: `person_name`, `from_role` and `to_role`; removals: `principal`, `email`, the access removed and `target`; plan actions: `principal` and `target` |
| `made_by`, `made_through` | `actor.name` (Polar Sky for `system`), `actor.surface` and `actor.assistant_client` |
| `approved_by`, `approved_at` | `approved_by.name` and `approved_by.at`; "Not recorded" for a removal or plan action without one; empty for events |
| `result` | removals: `result`; plan actions: `state`; empty for events |
| `reason` | `reason` |
| `confirmed_at`, `change_reference` | removals only |
| `before`, `after` | plan actions only, as compact JSON |
| `source` | `event`, `removal_record` or `plan` |

A CSV cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a single quote in front, as in the report skill. The Markdown table keeps each cell on one line and escapes Markdown formatting characters.

## Test

From the root of the install repository:

```sh
python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-audit-trail/tests
```

After an intended change to the output, rewrite the golden files and check the diff:

```sh
UPDATE_GOLDEN=1 python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-audit-trail/tests
git diff plugins/polar-sky-access-reviews/skills/access-review-audit-trail/tests/golden
```
