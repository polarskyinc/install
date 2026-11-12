# Report data folder

The renderer reads either a folder or one JSON file.

- Folder: `inputs.json` plus `responses/*.json`, read in file name order.
- File: `{"inputs": {...}, "responses": [...]}` with the same content. The test fixture `tests/fixtures/northwind.json` uses this form.

## responses

Each response is one tool call, copied unchanged:

```json
{"tool": "list_control_members", "arguments": {"control_id": "…", "limit": 100}, "response": {…}}
```

| Tool | Fields the renderer reads |
|---|---|
| `get_access_review_evidence` | `kept_direct_shares_as_of`; `controls[]`: `control_id`, `name`, `status`, `folders`, `approvals[]` (`at`, `carried_into_range`, `actor.type`, `actor.name`, `actor.surface`, `actor.assistant_client`), `kept_direct_shares[]` (`person`, `email`, `item_kind`, `item`, `role`), `removals[]` (`source`, `action`, `step`, `target_kind`, `target`, `principal`, `role`, `link_scope`, `state`, `at`, `reason`; a removal record has `grantee_kind` for `target_kind`, `result` (`removed`, `failed` or `pending`) for `state`, `confirmed_at`, and may have `role`, or `from_role` and `to_role` for a lowering, shown as "Edit → Read") |
| `get_control` | `control`: `id`, `provider`, `purpose`, `reason`, `folders[].site`, `folder_count` (more than the listed `folders` marks the site list incomplete), `kept_groups[]` and `dropped_groups[]` (`name`, `email`, `role`, `people_count`, `membership_incomplete`, `external_recipients`) |
| `list_control_members` | `control_id`; `members[]`: `id`, `name`, `email`, `title`, `department`, `role`, `is_owner`, `keeps_access`, `through_groups`, `individual_access`, `provenance` (`by`, `by_name`, `at`, `last_action`); and, once the tool returns them, `basis` and `account_type` |
| `get_control_activity` | `control_id`; `entries[]`: `at`, `type`. Changes in period counts the entries inside the period whose `type` the audit trail lists: `proposal_approved`, `proposal_reopened`, `proposal_superseded`, `member_added`, `member_removed`, `role_changed`, `made_owner`, `group_kept`, `group_dropped`, `plan_applied`, `plan_partially_applied` |
| `start_access_review_extract` | `extract_id`, `status`, `from`, `to` |
| `get_access_review_extract` | `extract_id`, `status` (`running`, `completed` or `failed`), `from`, `to`, `failure_reason`; once completed: `as_of`, `file` (`reference`, `sha256`, `bytes`, `format`), `controls`, `folders_read`, `rows`, `rows_by_kind`, `groups[]` (`name`, `kind` (`entra_group`, `sharepoint_group` or `google_group`), `counted_members`, `provider_member_count`, `nested_groups_match` (Google groups only: whether every group nested in it matched its own count too)), `exclusions[]` (`control_id`, `subject`, `reason`), `next_offset` (groups and exclusions share one offset, 25 of each per page) |
| `read_access_review_extract_rows` | `extract_id`, `status`, `sha256`, `next_cursor`, `sha256_verified` (cursor 0 only); `rows[]`: `control_name`, `folder`, `row_kind`, `grantee_type`, `principal_name`, `principal_email`, `login_name`, `roles`, `inherited`, `via_group_name`, `via_sharepoint_group_name`, `link_scope`, `link_type`, `link_expires_at`, `granted_on`, `group_owners_only`, `recipients_sampled`, `recipient_total_count`, `permission_id`, `principal_id`, `control_id`, `folder_item_id`, `drive_id`, `as_of` |

A response with `"refused": true` stops the render with its reason.

The render also stops, naming what is missing, when:

- a paged call stops early: a `next_offset` (evidence, members) or `next_cursor` (activity) has no response with that `offset` or `cursor` in its `arguments`. Activity may stop at a page whose oldest entry is older than the period start;
- the evidence date ranges (`arguments.from` and `arguments.to`) leave part of the review period out, or reach outside it;
- a control in the evidence has no `get_control`, `list_control_members` or `get_control_activity` response;
- the extract is still running: its last `start_access_review_extract` or `get_access_review_extract` response says `running`;
- the extract's days reach outside the review period;
- a completed extract misses a `get_access_review_extract` page (`offset` to `next_offset` from 0) or a `read_access_review_extract_rows` page (`cursor` to `next_cursor` from 0).

The extract: the render uses the extract named in the last extract response, by file order. With none, the report marks it "Not available in this version". A failed extract is shown as failed with its `failure_reason`, and the rest of the report renders. A completed extract fills Section 3 and Attachment F. The render does not refuse, but says plainly in Section 3, when a group's `counted_members` differs from its `provider_member_count` or a Google group's `nested_groups_match` is false, when the rows read differ from `rows` or `rows_by_kind`, when a rows page names another SHA-256 than `file.sha256`, or when `sha256_verified` is false.

No folder sets: when the evidence lists no control, the report still renders. Section 1 and the first line of the summary block say once that Polar Sky recorded no folder sets with an access approval in force in the period, so there was no access to review; the rows that depend on folder sets say "No folder sets", "No members", "No removals" and so on, and the figure cards and the outcome chart are left out.

When an approval ended: the first `get_control_activity` entry of type `proposal_reopened` (withdrawn), `proposal_superseded` (replaced by a later approval) or `proposal_dismissed` (rejected) after the approval, before the control's next approval and before the period ends, as the evidence tool decides which approvals were in force. The report calls each control a folder set. A control whose last approval in the evidence ended this way is counted as "approved, then withdrawn" (a person withdrew the approval and the folder set went back to awaiting review; or replaced by a later approval, or rejected), not as approved; its row says, for example, "Approved 2026-08-04, withdrawn 2026-10-19", and its members who keep access say "Yes, approved only until the approval was withdrawn 2026-10-19". A member whose `provenance.at` is after the end was decided later, so the report says, for example, "Added or changed 2026-10-25, after the approval was withdrawn 2026-10-19", and does not count them as having kept access while it was approved.

Who decided a member: `provenance.by` `system` is "Polar Sky" (it proposed the member; an approval of the folder set that included them is the decision); `user` is `provenance.by_name`. The date is `provenance.at`.

Reason: the member's `basis` if present, in words for the tags the import uses (`owner`, `predicted`, `group_expansion`, `existing_group_grant`, `direct_grant`, `service_account`); otherwise "Proposed by Polar Sky: " and the control's `reason` for a member Polar Sky proposed, and "Added or changed by " and the person's name for one a person decided.

## inputs.json

| Field | Required | Example |
|---|---|---|
| `organization` | yes | `Northwind Traders` |
| `report_id` | yes | `AR-2026-H2-0001` |
| `framework` | yes | `pci_dss`, `soc2`, `hipaa` or `sox` |
| `period` | yes | `{"from": "2026-05-01", "to": "2026-10-31"}` |
| `generated_at` | | Set by `render_report.py` from the clock each time it runs; a value in `inputs.json` is replaced. The time the member lists stand for only when the data is one JSON file and has no completed extract |
| `requested_by` | | `Steve Morgan, Director of Security Operations` |
| `procedure` | | `Northwind Traders User Access Review Procedure, version 3.2` |
| `removal_deadline` | | `30 days after the decision, per the review procedure` |
| `retention` | | `Report and attachments kept for 3 years, per the review procedure` |
| `review_interval` | SOC 2, SOX | `Quarterly` |
| `previous_review` | | `Completed 2026-04-30 in the previous access review tool` |
| `control_owner` | | `Laura Kim, Senior Manager, IT Compliance`; shown as Review owner |
| `data_source` | | `Microsoft 365 tenant contoso.onmicrosoft.com, read by Polar Sky` |
| `exclusions` | | `Global administrators, reviewed in the privileged access review` |
| `prepared_for` | | Defaults to the framework's text |
| `issued_at` | | `2026-11-03T09:45:00Z`; defaults to `generated_at` |
| `running_footer` | | Defaults to `Confidential.` |
| `acknowledgment` | | `{"name": "…", "title": "…", "date": "2026-11-03", "statement": "…"}` |
| `session` | | `{"id": "…", "source": "CLAUDE_CODE_SESSION_ID"}`; the report shows the id only |
| `columns` | | `{"members": ["folder_set", "person_name", …]}`; ids from `columns.json`, in the order to show; a table left out keeps its defaults |
| `logo` | | `/Users/laura/Documents/northwind-logo.png`; the full path of a PNG, JPEG or SVG file for the cover. `~` is expanded; a relative path is read from the folder the render runs in |

The skill asks for `requested_by`, `procedure`, `removal_deadline`, `retention` and `acknowledgment` (and `review_interval` for SOC 2 and SOX); when one is missing the report shows TBD and the summary block lists it. The fields step 2 of the skill marks optional (`control_owner`, `previous_review`, `data_source`, `exclusions`, `prepared_for`, `logo`) never show TBD: with no `control_owner`, `previous_review` or `exclusions` the report leaves its row out, `data_source` and `prepared_for` take their defaults, and with no logo the cover shows none.

The logo: the render refuses a file that does not exist, is larger than 2 MB, does not end in `.png`, `.jpg`, `.jpeg` or `.svg`, or whose first bytes are not those of the type its name says (PNG and JPEG signatures; for SVG, an `<svg` element first, after an optional XML declaration, comments and SVG doctype). It puts the file into `report.html` as a `data:` URI in an `<img>` element, so the HTML and the PDF carry the logo with them and the render writes no other file. A browser shows an SVG in an `<img>` element as a picture only: it runs no script in it and loads nothing it links to, so the SVG is not changed or cleaned. The logo is scaled to fit a 1.7 by 0.6 inch box on the cover.

## Output

`report.html`, `fonts/`, and one CSV per table: `members.csv`, `groups.csv`, `shares.csv`, `removals.csv`, `approvals.csv`, and `extract.csv` when there is a completed extract. `extract.csv` holds the extract's rows in the stored file's order; it is a rendering of the stored file, so its SHA-256 differs from the stored file's, and Attachment F lists both. CSV files are UTF-8 without a byte order mark, CRLF line ends, quoted only where needed (RFC 4180), and use the column ids as the header. A cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a single quote in front, so a spreadsheet does not run it as a formula (OWASP CSV injection guidance); the HTML shows the value unchanged. Members are labeled as at report time, not as at the end of the period, because `list_control_members` returns the members a control has now: the `as_of` column in `members.csv` and the member headings in the HTML carry the extract's `as_of` when there is a completed extract; otherwise, for a data folder, the time the last `list_control_members` file in `responses/` was saved (its modification time), so a later render keeps the read time; and for a single data file, `generated_at`. Kept direct shares carry, in the `read_at` column, the `kept_direct_shares_as_of` of the evidence response they were last read from. The chosen columns also set the HTML tables for groups, kept direct shares and removals. `make_pdf.py` adds `report.pdf`; a render removes the `report.pdf` an earlier render left, so an old PDF never sits next to a new HTML report.
