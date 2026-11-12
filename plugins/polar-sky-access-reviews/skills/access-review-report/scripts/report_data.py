"""Load the report data file and derive the rows and counts the report shows."""

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone

SKILL_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCES_DIRECTORY = os.path.join(SKILL_DIRECTORY, "references")

TOOL_EVIDENCE = "get_access_review_evidence"
TOOL_CONTROL = "get_control"
TOOL_MEMBERS = "list_control_members"
TOOL_ACTIVITY = "get_control_activity"
TOOL_EXTRACT_START = "start_access_review_extract"
TOOL_EXTRACT_GET = "get_access_review_extract"
TOOL_EXTRACT_ROWS = "read_access_review_extract_rows"

SAVED_AT = "_saved_at"

EXTRACT_COMPLETED = "completed"
EXTRACT_FAILED = "failed"

ROW_KIND_LABELS = {
    "grant": "grant",
    "link": "link",
    "group_member": "group member",
    "sharepoint_group_member": "SharePoint group member",
}

GROUP_KIND_LABELS = {"entra_group": "Entra group", "sharepoint_group": "SharePoint group", "google_group": "Google group"}

GOOGLE_GROUP = "google_group"

GROUP_KIND_PROVIDERS = {"entra_group": "microsoft365", "sharepoint_group": "microsoft365", GOOGLE_GROUP: "google_workspace"}

ROW_KIND_PROVIDERS = {"sharepoint_group_member": "microsoft365"}

UNKNOWN_PROVIDER_LABEL = "the provider"

NESTED_GROUP_DIFFERS = "Differs in a nested group"

PROVIDER_LABELS = {
    "microsoft365": ("Microsoft 365", "Microsoft 365 tenant"),
    "google_workspace": ("Google Workspace", "Google Workspace domain"),
}

SURFACE_LABELS = {"console": "Polar Sky console", "connector": "AI assistant"}

STATE_LABELS = {
    "applied": "Applied",
    "failed": "Failed",
    "pending": "Pending",
    "checked": "Pending",
    "sending": "Pending",
    "stale": "Not applied: the access had changed since Polar Sky prepared the removal, so Polar Sky left it as it was",
    "skipped": "Not applied: Polar Sky left this change for the organization's own IT team to carry out",
}

PENDING_STATES = {"pending", "checked", "sending"}

RESULT_STATES = {"removed": "applied", "failed": "failed", "pending": "pending"}

LOWER_ACCESS_ACTION = "Lower access"

RESULT_LABELS = {"removed": "Removed", "failed": "Failed", "pending": "Pending"}

ROLE_LABELS = {
    "reader": "Viewer", "writer": "Editor", "owner": "Owner", "commenter": "Commenter", "read": "Read", "write": "Edit",
}

TARGET_KIND_LABELS = {
    "user": "Person", "group": "Group", "site_group": "SharePoint group", "application": "Application",
    "domain": "Domain", "anyone": "Anyone with the link", "anonymous": "Anyone with the link", "link": "Sharing link",
    "file": "File", "folder": "Folder", "library": "Library", "shared_drive": "Shared drive",
}

BASIS_LABELS = {
    "owner": "Data owner",
    "predicted": "Predicted by Polar Sky from the person's work",
    "group_expansion": "Member of a group kept on the folders",
    "existing_group_grant": "Had access through a group before the review",
    "direct_grant": "Had a direct share before the review",
    "service_account": "Service account",
}

AUDIT_TRAIL_EVENT_TYPES = frozenset({
    "proposal_approved", "proposal_reopened", "proposal_superseded", "member_added", "member_removed",
    "role_changed", "made_owner", "group_kept", "group_dropped", "plan_applied", "plan_partially_applied",
})

APPROVAL_ENDINGS = {
    "proposal_reopened": "withdrawn",
    "proposal_superseded": "replaced by a later approval",
    "proposal_dismissed": "rejected",
}

CONTROL_APPROVED = "approved"
CONTROL_CARRIED = "carried"
CONTROL_ENDED = "ended"

POLICY_LABEL = "Polar Sky"
KEPT_BY_POLICY = "Proposed by Polar Sky"
KEPT_BY_PERSON = "Added or changed by"

DEFAULT_ACKNOWLEDGMENT = (
    "I acknowledge that, to the best of my knowledge, the access that remains to the data in this report "
    "is appropriate."
)


LOGO_MAXIMUM_BYTES = 2 * 1024 * 1024
LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
LOGO_TYPE_NAMES = {"image/png": "PNG", "image/jpeg": "JPEG", "image/svg+xml": "SVG"}
SVG_START = re.compile(
    rb"\A(?:\xef\xbb\xbf)?\s*(?:<\?xml[^>]*\?>\s*)?(?:(?:<!--(?:(?!-->).)*-->|<!DOCTYPE\s+svg[^>\[]*>)\s*)*<svg[\s>]",
    re.DOTALL,
)
SVG_START_BYTES = 64 * 1024


class ReportDataError(ValueError):
    """Raised when the data file is missing something the report needs or holds a refused tool call."""


def logo_type(content):
    """Name the image type a logo file's first bytes show, or None when it is not PNG, JPEG or SVG."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if SVG_START.match(content[:SVG_START_BYTES]):
        return "image/svg+xml"
    return None


def load_logo(path):
    """Read the customer logo file into a data URI for the cover, or return None when no logo was given."""
    if path in (None, ""):
        return None
    if not isinstance(path, str):
        raise ReportDataError("inputs.logo must be the path to a logo file.")
    full_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(full_path):
        raise ReportDataError(f"The logo file {full_path} does not exist. Give another file, or no logo.")
    extension = os.path.splitext(full_path)[1].lower()
    if extension not in LOGO_TYPES:
        raise ReportDataError(
            f"The logo file {full_path} is not a PNG, JPEG or SVG file. Give a .png, .jpg, .jpeg or .svg file, or no logo."
        )
    try:
        with open(full_path, "rb") as handle:
            content = handle.read(LOGO_MAXIMUM_BYTES + 1)
    except OSError as error:
        raise ReportDataError(
            f"The logo file {full_path} cannot be read ({error.strerror or error}). Give another file, or no logo."
        ) from error
    if len(content) > LOGO_MAXIMUM_BYTES:
        raise ReportDataError(f"The logo file {full_path} is larger than 2 MB. Give a smaller file, or no logo.")
    expected = LOGO_TYPES[extension]
    if logo_type(content) != expected:
        raise ReportDataError(
            f"The logo file {full_path} is not a {LOGO_TYPE_NAMES[expected]} image, though its name ends in {extension}. "
            "Give a PNG, JPEG or SVG file, or no logo."
        )
    return f"data:{expected};base64,{base64.b64encode(content).decode('ascii')}"


def load_reference(name):
    """Read one JSON file from the skill's references folder."""
    with open(os.path.join(REFERENCES_DIRECTORY, name), encoding="utf-8") as handle:
        return json.load(handle)


def load_data(path):
    """Read a data file, or a folder holding inputs.json and responses/*.json, into one dictionary."""
    if os.path.isdir(path):
        with open(os.path.join(path, "inputs.json"), encoding="utf-8") as handle:
            inputs = json.load(handle)
        responses = []
        responses_directory = os.path.join(path, "responses")
        for name in sorted(os.listdir(responses_directory)):
            if name.endswith(".json"):
                file_path = os.path.join(responses_directory, name)
                with open(file_path, encoding="utf-8") as handle:
                    entry = json.load(handle)
                saved_at = datetime.fromtimestamp(os.path.getmtime(file_path), timezone.utc).replace(microsecond=0)
                entry[SAVED_AT] = saved_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                responses.append(entry)
        return {"inputs": inputs, "responses": responses}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value):
    """Parse an RFC 3339 time as Go writes it, nanoseconds included, into an aware UTC datetime."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    match = re.match(r"^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", text)
    if match:
        fraction = "." + match.group(2)[1:7].ljust(6, "0") if match.group(2) else ""
        text = match.group(1) + fraction + match.group(3)
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def role_label(value):
    """Name a provider role the way the member lists do, such as Viewer for reader, keeping any other value."""
    return ROLE_LABELS.get(value or "", value or "")


def target_kind_label(value):
    """Name what a removal acted on in plain words, such as Person for user, or any other value with spaces for underscores."""
    value = value or ""
    if value in TARGET_KIND_LABELS:
        return TARGET_KIND_LABELS[value]
    readable = value.replace("_", " ")
    return readable[:1].upper() + readable[1:]


def format_date(value):
    """Format a time or date string as YYYY-MM-DD in UTC, or an empty string."""
    if not value:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
        return str(value)
    return parse_time(value).strftime("%Y-%m-%d")


def format_time(value):
    """Format a time as YYYY-MM-DD HH:MM UTC, or an empty string."""
    if not value:
        return ""
    return parse_time(value).strftime("%Y-%m-%d %H:%M UTC")


def _period_bounds(period):
    start = datetime.fromisoformat(period["from"]).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(period["to"]).replace(tzinfo=timezone.utc) + timedelta(days=1)
    return start, end


def _check_response(entry):
    response = entry.get("response") or {}
    if response.get("refused"):
        raise ReportDataError(
            f"{entry.get('tool')} was refused ({response.get('reason')}): {response.get('message')}"
        )
    return response


def _control_id_of(entry, response):
    return response.get("control_id") or (entry.get("arguments") or {}).get("control_id")


def _join(values):
    return "; ".join(str(value) for value in values if value not in (None, ""))


def _yes_no(value):
    return "Yes" if value else "No"


def _approval_actor_name(approval):
    actor = approval.get("actor") or {}
    if actor.get("type") == "system":
        return "Polar Sky"
    return actor.get("name") or "an unknown account"


def _approval_identity(approval):
    return approval.get("at"), json.dumps(approval.get("actor") or {}, sort_keys=True)


def _merge_evidence_control(evidence_controls, control, shares_read_at):
    """Add a control from one evidence page, joining approvals and removals across date ranges and keeping the last kept direct shares read, with their read time."""
    known = evidence_controls.get(control["control_id"])
    if known is None:
        evidence_controls[control["control_id"]] = {
            **control,
            **{key: list(control.get(key) or []) for key in ("approvals", "kept_direct_shares", "removals")},
            "shares_read_at": shares_read_at,
        }
        return
    for approval in control.get("approvals") or []:
        same = [index for index, kept in enumerate(known["approvals"]) if _approval_identity(kept) == _approval_identity(approval)]
        if not same:
            known["approvals"].append(approval)
        elif known["approvals"][same[0]].get("carried_into_range") and not approval.get("carried_into_range"):
            known["approvals"][same[0]] = approval
    for removal in control.get("removals") or []:
        if removal not in known["removals"]:
            known["removals"].append(removal)
    if "kept_direct_shares" in control:
        known["kept_direct_shares"] = list(control["kept_direct_shares"] or [])
        known["shares_read_at"] = shares_read_at


def collect(data):
    """Group the tool responses by control and return the raw records the report is built from."""
    evidence_controls = {}
    shares_read_at = None
    controls = {}
    members = {}
    activity = {}
    extracts = {}
    tools_called = set()
    pages = {TOOL_EVIDENCE: {}, TOOL_MEMBERS: {}, TOOL_ACTIVITY: {}}
    for entry in data.get("responses", []):
        tool = entry.get("tool")
        tools_called.add(tool)
        response = _check_response(entry)
        arguments = entry.get("arguments") or {}
        if tool == TOOL_EVIDENCE:
            page_read_at = response.get("kept_direct_shares_as_of")
            shares_read_at = page_read_at or shares_read_at
            date_range = (arguments.get("from") or response.get("from"), arguments.get("to") or response.get("to"))
            pages[TOOL_EVIDENCE].setdefault(date_range, {})[_offset_of(arguments, response)] = response.get("next_offset")
            for control in response.get("controls", []):
                _merge_evidence_control(evidence_controls, control, page_read_at)
        elif tool == TOOL_CONTROL:
            control = response.get("control") or {}
            controls[control.get("id")] = control
        elif tool == TOOL_MEMBERS:
            control_id = _control_id_of(entry, response)
            pages[TOOL_MEMBERS].setdefault(control_id, {})[_offset_of(arguments, response)] = response.get("next_offset")
            listed = members.setdefault(control_id, {})
            for member in response.get("members", []):
                listed[member.get("id") or member.get("email")] = member
        elif tool == TOOL_ACTIVITY:
            control_id = _control_id_of(entry, response)
            entries = response.get("entries", [])
            oldest = min((parse_time(item.get("at")) for item in entries if item.get("at")), default=None)
            pages[TOOL_ACTIVITY].setdefault(control_id, {})[arguments.get("cursor")] = (response.get("next_cursor"), oldest)
            activity.setdefault(control_id, []).extend(entries)
        elif tool in (TOOL_EXTRACT_START, TOOL_EXTRACT_GET, TOOL_EXTRACT_ROWS):
            _collect_extract(extracts, tool, arguments, response)
    if TOOL_EVIDENCE not in tools_called:
        raise ReportDataError(f"The data file holds no {TOOL_EVIDENCE} response.")
    return {
        "evidence_controls": evidence_controls,
        "shares_read_at": shares_read_at,
        "controls": controls,
        "members": members,
        "activity": activity,
        "extracts": extracts,
        "pages": pages,
    }


def _collect_extract(extracts, tool, arguments, response):
    """Add one extract tool response to the extract it names, keeping the last status seen and every page."""
    extract_id = response.get("extract_id") or arguments.get("extract_id")
    if not extract_id:
        raise ReportDataError(f"A {tool} response names no extract_id.")
    record = extracts.setdefault(extract_id, {
        "id": extract_id, "status": None, "from": None, "to": None, "failure_reason": None,
        "summary_pages": {}, "row_pages": {},
    })
    record["last_seen"] = _next_sequence(extracts)
    for key in ("from", "to"):
        record[key] = response.get(key) or record[key]
    status = response.get("status")
    if status:
        record["status"] = status
    if tool == TOOL_EXTRACT_GET and status == EXTRACT_FAILED:
        record["failure_reason"] = response.get("failure_reason") or ""
    if tool == TOOL_EXTRACT_GET and status == EXTRACT_COMPLETED:
        record["summary_pages"][_offset_of(arguments, response)] = response
    if tool == TOOL_EXTRACT_ROWS and status == EXTRACT_COMPLETED:
        record["row_pages"][_cursor_of(arguments, response)] = response


def _next_sequence(extracts):
    return max((record.get("last_seen") or 0 for record in extracts.values()), default=0) + 1


def _cursor_of(arguments, response):
    cursor = arguments.get("cursor")
    if cursor is None:
        cursor = response.get("cursor")
    return cursor or 0


def _offset_of(arguments, response):
    return arguments.get("offset") or response.get("offset") or 0


def _check_offset_pages(offsets, label):
    offset = 0
    seen = set()
    while offset is not None:
        if offset not in offsets:
            which = "first page" if offset == 0 else f"page at offset {offset}"
            raise ReportDataError(
                f"{label} is missing its {which}. Fetch every page, with offset set to next_offset, until next_offset is null."
            )
        if offset in seen:
            raise ReportDataError(f"{label} repeats the page at offset {offset}.")
        seen.add(offset)
        offset = offsets[offset]


def _check_activity_pages(cursors, label, period_start):
    cursor = None
    seen = set()
    while True:
        if cursor not in cursors:
            which = "first page" if cursor is None else f"page at cursor {cursor}"
            raise ReportDataError(
                f"{label} is missing its {which}. Fetch every page, with cursor set to next_cursor, until next_cursor "
                "is null or the entries are older than the period start."
            )
        if cursor in seen:
            raise ReportDataError(f"{label} repeats the page at cursor {cursor}.")
        seen.add(cursor)
        next_cursor, oldest = cursors[cursor]
        if next_cursor is None or (oldest is not None and oldest < period_start):
            return
        cursor = next_cursor


def _check_period_covered(date_ranges, period):
    first_day = datetime.fromisoformat(period["from"]).date()
    last_day = datetime.fromisoformat(period["to"]).date()
    covered_until = first_day
    usable = []
    for start, end in date_ranges:
        if not start or not end:
            raise ReportDataError(f"A {TOOL_EVIDENCE} response has no from and to dates in its arguments.")
        start_day = datetime.fromisoformat(start).date()
        end_day = datetime.fromisoformat(end).date()
        if start_day < first_day or end_day > last_day:
            raise ReportDataError(
                f"{TOOL_EVIDENCE} for {start} to {end} reaches outside the review period "
                f"{period['from']} to {period['to']}. Call it only for dates inside the period."
            )
        usable.append((start_day, end_day))
    for start, end in sorted(usable):
        if start <= covered_until <= end:
            covered_until = end + timedelta(days=1)
    if covered_until <= last_day:
        raise ReportDataError(
            f"No {TOOL_EVIDENCE} response covers {covered_until.isoformat()} to {last_day.isoformat()}. "
            "Call it for every part of the review period, 366 days or less at a time."
        )


def check_complete(records, period):
    """Refuse a data folder whose paged responses stop early or that lacks a control's responses."""
    period_start, _ = _period_bounds(period)
    evidence_pages = records["pages"][TOOL_EVIDENCE]
    for (start, end), offsets in sorted(evidence_pages.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))):
        _check_offset_pages(offsets, f"{TOOL_EVIDENCE} for {start} to {end}")
    _check_period_covered(evidence_pages, period)
    for control_id in sorted(records["evidence_controls"]):
        if control_id not in records["controls"]:
            raise ReportDataError(f"The data holds no {TOOL_CONTROL} response for control {control_id}.")
        member_pages = records["pages"][TOOL_MEMBERS].get(control_id)
        if member_pages is None:
            raise ReportDataError(f"The data holds no {TOOL_MEMBERS} response for control {control_id}.")
        _check_offset_pages(member_pages, f"{TOOL_MEMBERS} for control {control_id}")
        activity_pages = records["pages"][TOOL_ACTIVITY].get(control_id)
        if activity_pages is None:
            raise ReportDataError(f"The data holds no {TOOL_ACTIVITY} response for control {control_id}.")
        _check_activity_pages(activity_pages, f"{TOOL_ACTIVITY} for control {control_id}", period_start)


def latest_extract(records):
    """Return the extract the report uses, the last one the responses name, or None when there are no extract responses."""
    if not records["extracts"]:
        return None
    return max(records["extracts"].values(), key=lambda record: record["last_seen"])


def _check_cursor_pages(pages, label):
    cursor = 0
    seen = set()
    while cursor is not None:
        if cursor not in pages:
            which = "first page" if cursor == 0 else f"page at cursor {cursor}"
            raise ReportDataError(
                f"{label} is missing its {which}. Fetch every page, starting at cursor 0, with cursor set to "
                "next_cursor, until next_cursor is null."
            )
        if cursor in seen:
            raise ReportDataError(f"{label} repeats the page at cursor {cursor}.")
        seen.add(cursor)
        cursor = pages[cursor].get("next_cursor")


def check_extract(extract, period):
    """Refuse an extract still running, outside the review period, or whose summary or row pages stop early."""
    if extract is None:
        return
    label = f"Extract {extract['id']}"
    if extract["status"] not in (EXTRACT_COMPLETED, EXTRACT_FAILED):
        raise ReportDataError(
            f"{label} has no {TOOL_EXTRACT_GET} response that says it completed or failed. Call {TOOL_EXTRACT_GET} "
            "until its status is completed or failed."
        )
    if extract["from"] and extract["to"] and (extract["from"] < period["from"] or extract["to"] > period["to"]):
        raise ReportDataError(
            f"{label} covers {extract['from']} to {extract['to']}, outside the review period "
            f"{period['from']} to {period['to']}. Start it only for days inside the period."
        )
    if extract["status"] != EXTRACT_COMPLETED:
        return
    offsets = {offset: page.get("next_offset") for offset, page in extract["summary_pages"].items()}
    _check_offset_pages(offsets, f"{TOOL_EXTRACT_GET} for extract {extract['id']}")
    _check_cursor_pages(extract["row_pages"], f"{TOOL_EXTRACT_ROWS} for extract {extract['id']}")


def _chain(pages, start, next_key):
    ordered = []
    key = start
    while key is not None:
        ordered.append(pages[key])
        key = pages[key].get(next_key)
    return ordered


def _extract_row(row):
    return {
        "folder_set": row.get("control_name") or "",
        "folder": row.get("folder") or "",
        "row_kind": ROW_KIND_LABELS.get(row.get("row_kind") or "", row.get("row_kind") or ""),
        "grantee_type": (row.get("grantee_type") or "").replace("_", " "),
        "principal_name": row.get("principal_name") or "",
        "principal_email": row.get("principal_email") or "",
        "login_name": row.get("login_name") or "",
        "roles": _join(row.get("roles") or []),
        "inherited": _yes_no(row.get("inherited")),
        "via_group": row.get("via_group_name") or row.get("via_sharepoint_group_name") or "",
        "link_scope": row.get("link_scope") or "",
        "link_type": row.get("link_type") or "",
        "link_expires_at": format_time(row.get("link_expires_at")),
        "granted_on": row.get("granted_on") or "",
        "group_owners_only": _yes_no(row.get("group_owners_only")),
        "recipients_sampled": _yes_no(row.get("recipients_sampled")),
        "recipient_total_count": str(row["recipient_total_count"]) if row.get("recipient_total_count") else "",
        "permission_id": row.get("permission_id") or "",
        "principal_id": row.get("principal_id") or "",
        "folder_set_id": row.get("control_id") or "",
        "folder_item_id": row.get("folder_item_id") or "",
        "drive_id": row.get("drive_id") or "",
        "as_of": format_time(row.get("as_of")),
        "_kind": row.get("row_kind") or "",
    }


def _group_count_row(group):
    counted = group.get("counted_members") or 0
    provider_count = group.get("provider_member_count")
    provider = GROUP_KIND_PROVIDERS.get(group.get("kind") or "")
    provider_label = PROVIDER_LABELS[provider][0] if provider else UNKNOWN_PROVIDER_LABEL
    if provider_count is None:
        result = f"No count from {provider_label}"
    elif provider_count != counted:
        result = "Differs"
    elif group.get("nested_groups_match") is False:
        result = NESTED_GROUP_DIFFERS
    else:
        result = "Matches"
    return {
        "provider": provider,
        "provider_label": provider_label,
        "group_name": group.get("name") or group.get("group_id") or "",
        "kind": GROUP_KIND_LABELS.get(group.get("kind") or "", (group.get("kind") or "").replace("_", " ")),
        "counted_members": counted,
        "provider_member_count": provider_count,
        "result": result,
    }


def _kind_counts(counts):
    return [
        (ROW_KIND_LABELS.get(kind, kind.replace("_", " ")), count or 0)
        for kind, count in sorted((counts or {}).items())
    ]


def build_extract(extract, control_names):
    """Turn the chosen extract's responses into what the report shows of it, or None when there is none."""
    if extract is None:
        return None
    model = {
        "id": extract["id"],
        "status": extract["status"],
        "from": extract["from"] or "",
        "to": extract["to"] or "",
        "failure_reason": extract["failure_reason"] or "",
    }
    if extract["status"] != EXTRACT_COMPLETED:
        return model
    summaries = _chain(extract["summary_pages"], 0, "next_offset")
    first = summaries[0]
    row_pages = _chain(extract["row_pages"], 0, "next_cursor")
    rows = [_extract_row(row) for page in row_pages for row in page.get("rows") or []]
    read_by_kind = {}
    for row in rows:
        read_by_kind[row["_kind"]] = read_by_kind.get(row["_kind"], 0) + 1
    file = first.get("file") or {}
    groups = [_group_count_row(group) for page in summaries for group in page.get("groups") or []]
    exclusions = [
        {
            "folder_set": control_names.get(item.get("control_id"), item.get("control_id")) if item.get("control_id") else "The whole extract",
            "subject": item.get("subject") or "",
            "reason": item.get("reason") or "",
        }
        for page in summaries
        for item in page.get("exclusions") or []
    ]
    row_hashes = {page.get("sha256") for page in row_pages}
    model.update({
        "as_of": first.get("as_of") or "",
        "file": {key: file.get(key) for key in ("reference", "sha256", "bytes", "format")},
        "controls": first.get("controls"),
        "folders_read": first.get("folders_read"),
        "rows": first.get("rows") or 0,
        "rows_by_kind": _kind_counts(first.get("rows_by_kind")),
        "rows_read": len(rows),
        "rows_read_by_kind": _kind_counts(read_by_kind),
        "rows_read_match": len(rows) == (first.get("rows") or 0) and read_by_kind == {
            kind: count for kind, count in (first.get("rows_by_kind") or {}).items() if count
        },
        "row_hashes_match": row_hashes == {file.get("sha256")},
        "sha256_verified": row_pages[0].get("sha256_verified"),
        "groups": groups,
        "groups_differ": [group for group in groups if group["result"] in ("Differs", NESTED_GROUP_DIFFERS)],
        "groups_without_provider_count": sum(1 for group in groups if group["provider_member_count"] is None),
        "exclusions": exclusions,
        "exclusion_control_ids": [
            item["control_id"] for page in summaries for item in page.get("exclusions") or [] if item.get("control_id")
        ],
        "table": rows,
    })
    return model


def _member_reason(member, control_reason, decided_by_policy, decided_by):
    basis = (member.get("basis") or "").strip()
    if basis:
        if basis in BASIS_LABELS:
            return BASIS_LABELS[basis]
        spaced = basis.replace("_", " ") if " " not in basis else basis
        return spaced[:1].upper() + spaced[1:]
    if decided_by_policy:
        return f"{KEPT_BY_POLICY}: {control_reason}" if control_reason else KEPT_BY_POLICY
    return f"{KEPT_BY_PERSON} {decided_by}"


def _member_row(control_entry, member, members_as_of):
    provenance = member.get("provenance") or {}
    keeps_access = _yes_no(member.get("keeps_access"))
    kept_until_ended = False
    if member.get("keeps_access") and control_entry["state"] == CONTROL_ENDED:
        decided_at = parse_time(provenance.get("at"))
        if decided_at and decided_at > control_entry["ended_at"]:
            keeps_access = (
                f"Added or changed {decided_at.strftime('%Y-%m-%d')}, after the approval was "
                f"{control_entry['ended_how']} {control_entry['ended_on']}"
            )
        else:
            kept_until_ended = True
            keeps_access = f"Yes, approved only until the approval was {control_entry['ended_how']} {control_entry['ended_on']}"
    decided_by_policy = provenance.get("by") == "system"
    decided_by = POLICY_LABEL if decided_by_policy else (provenance.get("by_name") or "an unknown account")
    return {
        "folder_set": control_entry["name"],
        "folders": _join(control_entry["folders"]),
        "person_name": member.get("name") or member.get("email") or "an unknown person",
        "email": member.get("email") or "",
        "title": member.get("title") or "",
        "department": member.get("department") or "",
        "account_type": member.get("account_type") or "",
        "role": member.get("role") or "",
        "through_groups": _join(member.get("through_groups") or []),
        "individual_access": _yes_no(member.get("individual_access")),
        "keeps_access": keeps_access,
        "is_owner": _yes_no(member.get("is_owner")),
        "decided_by": decided_by,
        "decided_on": format_date(provenance.get("at")),
        "last_action": (provenance.get("last_action") or "").replace("_", " "),
        "reason": _member_reason(member, control_entry["reason"], decided_by_policy, decided_by),
        "reviewed_by": control_entry["approved_by"],
        "reviewed_on": control_entry["approved_on"],
        "as_of": format_time(members_as_of),
        "_decided_by_policy": decided_by_policy,
        "_keeps_access": bool(member.get("keeps_access")),
        "_kept_until_ended": kept_until_ended,
        "_has_account_type": bool(member.get("account_type")),
    }


def _group_rows(control_entry, control):
    rows = []
    for outcome, groups in (("Kept", control.get("kept_groups") or []), ("Dropped", control.get("dropped_groups") or [])):
        for group in groups:
            rows.append({
                "folder_set": control_entry["name"],
                "folders": _join(control_entry["folders"]),
                "group_name": group.get("name") or group.get("email") or "",
                "group_email": group.get("email") or "",
                "outcome": outcome,
                "role": group.get("role") or "",
                "people_count": "Not recorded" if group.get("people_count") is None else str(group["people_count"]),
                "membership_complete": _yes_no(not group.get("membership_incomplete")) if outcome == "Kept" else "",
                "external_recipients": _join(group.get("external_recipients") or []),
                "reviewed_by": control_entry["approved_by"],
                "reviewed_on": control_entry["approved_on"],
            })
    return sorted(rows, key=lambda row: (row["outcome"] != "Kept", row["group_name"].lower()))


def _share_rows(control_entry, evidence, read_at):
    rows = []
    for share in evidence.get("kept_direct_shares") or []:
        rows.append({
            "folder_set": control_entry["name"],
            "person_name": share.get("person") or "",
            "email": share.get("email") or "",
            "item_kind": (share.get("item_kind") or "").capitalize(),
            "item": share.get("item") or "",
            "role": role_label(share.get("role")),
            "read_at": format_time(read_at),
        })
    return sorted(rows, key=lambda row: (row["person_name"].lower(), row["item"]))


def _removal_role(removal):
    """Name the permission a removal took away, or the old and new permission of a lowering, such as Edit → Read."""
    from_role, to_role = removal.get("from_role"), removal.get("to_role")
    if from_role and to_role:
        return f"{role_label(from_role)} → {role_label(to_role)}"
    return role_label(removal.get("role") or from_role)


def _removal_rows(control_entry, evidence):
    rows = []
    for removal in evidence.get("removals") or []:
        result = removal.get("result") or ""
        state = removal.get("state") or RESULT_STATES.get(result, result)
        label = RESULT_LABELS.get(result) or STATE_LABELS.get(state, state.replace("_", " ").capitalize())
        if result == "removed" and removal.get("action") == LOWER_ACCESS_ACTION:
            label = "Lowered"
        rows.append({
            "folder_set": control_entry["name"],
            "folders": _join(control_entry["folders"]),
            "action": removal.get("action") or "",
            "step": removal.get("step") or "",
            "target_kind": target_kind_label(removal.get("target_kind") or removal.get("grantee_kind")),
            "target": removal.get("target") or "",
            "principal": removal.get("principal") or "",
            "role": _removal_role(removal),
            "link_scope": removal.get("link_scope") or "",
            "state": label,
            "state_at": format_date(removal.get("at")),
            "state_reason": removal.get("reason") or "",
            "confirmed_on": format_date(removal.get("confirmed_at")),
            "_state": state,
            "_confirmable": removal.get("source") == "removal_record",
            "_confirmed": bool(removal.get("confirmed_at")),
            "_at": removal.get("at") or "",
        })
    return sorted(rows, key=lambda row: (row["_at"], row["target"], row["step"]))


def _approval_endings(entries):
    """Return, oldest first, when the activity says an approval stopped being in force, with how it stopped."""
    endings = set()
    for entry in entries:
        how = APPROVAL_ENDINGS.get(entry.get("type") or "")
        at = parse_time(entry.get("at"))
        if how and at:
            endings.add((at, how))
    return sorted(endings)


def _approval_end(endings, approved_at, until):
    """Return the first ending after an approval and before the next approval or the period end, or None."""
    for at, how in endings:
        if approved_at < at < until:
            return at, how
    return None


def _approval_rows(control_entry, evidence, endings, period_end):
    rows = []
    approvals = sorted(evidence.get("approvals") or [], key=lambda approval: parse_time(approval.get("at")))
    for index, approval in enumerate(approvals):
        actor = approval.get("actor") or {}
        approved_at = parse_time(approval.get("at"))
        until = parse_time(approvals[index + 1].get("at")) if index + 1 < len(approvals) else period_end
        ended = _approval_end(endings, approved_at, until)
        rows.append({
            "folder_set": control_entry["name"],
            "folders": _join(control_entry["folders"]),
            "approved_by": _approval_actor_name(approval),
            "approved_at": format_time(approval.get("at")),
            "carried_into_period": _yes_no(approval.get("carried_into_range")),
            "surface": SURFACE_LABELS.get(actor.get("surface") or "", actor.get("surface") or ""),
            "assistant_client": actor.get("assistant_client") or "",
            "ended": f"{ended[1][:1].upper()}{ended[1][1:]} {ended[0].strftime('%Y-%m-%d')}" if ended else "",
            "_carried": bool(approval.get("carried_into_range")),
            "_at": approval.get("at") or "",
            "_ended_on": ended[0].strftime("%Y-%m-%d") if ended else "",
            "_ended_how": ended[1] if ended else "",
            "_ended_at": ended[0] if ended else None,
        })
    return rows


def _control_state(approvals):
    """Say whether a control's approval stood at the period end, ended in the period, or was only carried in."""
    if approvals and approvals[-1]["_ended_on"]:
        return CONTROL_ENDED
    if any(not row["_carried"] for row in approvals):
        return CONTROL_APPROVED
    return CONTROL_CARRIED


def approval_text(control):
    """Say when a control was last approved and, when that approval ended in the period, when and how it ended."""
    if not control["approved_on"]:
        return "Not recorded"
    text = f"Approved {control['approved_on']}"
    if control["state"] == CONTROL_ENDED:
        return f"{text}, {control['ended_how']} {control['ended_on']}"
    if control["state"] == CONTROL_CARRIED:
        return f"{text}, before the period, still in force"
    return text


def _activity_in_period(entries, period):
    """Return the control events in the period that the audit trail lists, each once."""
    start, end = _period_bounds(period)
    seen = set()
    kept = []
    for entry in entries:
        if entry.get("type") not in AUDIT_TRAIL_EVENT_TYPES:
            continue
        at = parse_time(entry.get("at"))
        key = json.dumps(entry, sort_keys=True)
        if at and start <= at < end and key not in seen:
            seen.add(key)
            kept.append(entry)
    return kept


def members_read_at(inputs, extract, responses):
    """Return the time the member lists stand for: a completed extract's as-of time, else when the last member list was saved, else the report generation time."""
    if extract and extract["status"] == EXTRACT_COMPLETED and extract.get("as_of"):
        return extract["as_of"]
    saved = [entry[SAVED_AT] for entry in responses if entry.get("tool") == TOOL_MEMBERS and entry.get(SAVED_AT)]
    return max(saved) if saved else inputs["generated_at"]


def extract_providers(extract, controls, report_providers):
    """The providers the returned data names: the kinds of the extract's groups and rows, the controls of its rows and exclusions, else the report's; empty when nothing names one."""
    found = {group["provider"] for group in extract.get("groups") or [] if group["provider"]}
    found |= {ROW_KIND_PROVIDERS[row["_kind"]] for row in extract.get("table") or [] if row["_kind"] in ROW_KIND_PROVIDERS}
    control_ids = [row["folder_set_id"] for row in extract.get("table") or []]
    control_ids += extract.get("exclusion_control_ids") or []
    for control_id in control_ids:
        provider = (controls.get(control_id) or {}).get("provider")
        if provider in PROVIDER_LABELS:
            found.add(provider)
    if not found:
        found = {provider for provider in report_providers if provider in PROVIDER_LABELS}
    return sorted(found)


def build_model(data):
    """Turn the data file into the rows, counts and texts the renderer lays out."""
    inputs = data.get("inputs") or {}
    for key in ("organization", "report_id", "framework", "period", "generated_at"):
        if not inputs.get(key):
            raise ReportDataError(f"inputs.{key} is required.")
    frameworks = load_reference("frameworks.json")
    if inputs["framework"] not in frameworks:
        raise ReportDataError(
            f"inputs.framework must be one of {', '.join(sorted(frameworks))}, not {inputs['framework']!r}."
        )
    records = collect(data)
    period = inputs["period"]
    check_complete(records, period)
    chosen_extract = latest_extract(records)
    check_extract(chosen_extract, period)
    extract = build_extract(
        chosen_extract,
        {control_id: control.get("name") or control_id for control_id, control in records["evidence_controls"].items()},
    )
    members_as_of = members_read_at(inputs, extract, data.get("responses", []))

    controls = []
    tables = {"members": [], "groups": [], "shares": [], "removals": [], "approvals": []}
    providers = set()
    sites = set()
    sites_complete = True
    for control_id, evidence in records["evidence_controls"].items():
        detail = records["controls"].get(control_id) or {}
        if detail.get("provider"):
            providers.add(detail["provider"])
        listed_folders = detail.get("folders") or []
        if (detail.get("folder_count") or 0) > len(listed_folders):
            sites_complete = False
        for folder in listed_folders:
            if folder.get("site"):
                sites.add(folder["site"])
        approvals = _approval_rows(
            {"name": evidence.get("name") or "", "folders": evidence.get("folders") or []},
            evidence,
            _approval_endings(records["activity"].get(control_id, [])),
            _period_bounds(period)[1],
        )
        latest = approvals[-1] if approvals else None
        entry = {
            "id": control_id,
            "name": evidence.get("name") or detail.get("name") or "",
            "status": evidence.get("status") or "",
            "folders": evidence.get("folders") or [],
            "reason": (detail.get("reason") or "").strip(),
            "purpose": (detail.get("purpose") or "").strip(),
            "approved_by": latest["approved_by"] if latest else "",
            "approved_on": format_date(latest["_at"]) if latest else "",
            "state": _control_state(approvals),
            "ended_on": latest["_ended_on"] if latest else "",
            "ended_how": latest["_ended_how"] if latest else "",
            "ended_at": latest["_ended_at"] if latest else None,
            "has_detail": bool(detail),
            "has_members": control_id in records["members"],
        }
        members = sorted(
            (_member_row(entry, member, members_as_of) for member in records["members"].get(control_id, {}).values()),
            key=lambda row: (row["person_name"].lower(), row["email"].lower()),
        )
        owners = [row["person_name"] for row in members if row["is_owner"] == "Yes"]
        entry["owner"] = owners[0] if owners else ""
        groups = _group_rows(entry, detail)
        shares = _share_rows(entry, evidence, evidence.get("shares_read_at") or records["shares_read_at"])
        removals = _removal_rows(entry, evidence)
        entry["activity_in_period"] = len(_activity_in_period(records["activity"].get(control_id, []), period))
        entry["counts"] = {
            "members": len(members),
            "kept_by_policy": sum(1 for row in members if row["_keeps_access"] and row["_decided_by_policy"]),
            "kept_by_person": sum(1 for row in members if row["_keeps_access"] and not row["_decided_by_policy"]),
            "keeps_nothing": sum(1 for row in members if not row["_keeps_access"]),
            "kept_until_ended": sum(1 for row in members if row["_kept_until_ended"]),
            "groups_kept": sum(1 for row in groups if row["outcome"] == "Kept"),
            "groups_dropped": sum(1 for row in groups if row["outcome"] == "Dropped"),
            "shares": len(shares),
            "removals": len(removals),
            "removals_applied": sum(1 for row in removals if row["_state"] == "applied"),
        }
        controls.append(entry)
        tables["members"].extend(members)
        tables["groups"].extend(groups)
        tables["shares"].extend(shares)
        tables["removals"].extend(removals)
        tables["approvals"].extend(approvals)

    controls.sort(key=lambda control: (control["name"].lower(), control["id"]))
    order = {control["name"]: index for index, control in enumerate(controls)}
    for name in tables:
        tables[name].sort(key=lambda row: order.get(row["folder_set"], 0))

    provider = sorted(providers)[0] if len(providers) == 1 else ""
    provider_label, provider_scope = PROVIDER_LABELS.get(provider, (provider or "the connected file systems", "file systems"))
    if len(providers) > 1:
        provider_label = " and ".join(PROVIDER_LABELS.get(item, (item, item))[0] for item in sorted(providers))
        provider_scope = provider_label + " tenants"

    if extract:
        extract["providers"] = extract_providers(extract, records["controls"], providers)
    return {
        "inputs": inputs,
        "framework_key": inputs["framework"],
        "framework": frameworks[inputs["framework"]],
        "period": period,
        "provider_label": provider_label,
        "provider_scope": provider_scope,
        "sites": sorted(sites),
        "sites_complete": sites_complete,
        "controls": controls,
        "tables": tables,
        "shares_read_at": records["shares_read_at"],
        "members_as_of": members_as_of,
        "issued_at": inputs.get("issued_at") or inputs["generated_at"],
        "extract": extract,
        "acknowledgment": inputs.get("acknowledgment") or {},
        "logo": load_logo(inputs.get("logo")),
        "totals": _totals(controls, tables),
    }


def _totals(controls, tables):
    totals = {key: sum(control["counts"][key] for control in controls) for key in controls[0]["counts"]} if controls else {
        key: 0 for key in ("members", "kept_by_policy", "kept_by_person", "keeps_nothing", "kept_until_ended", "groups_kept",
                           "groups_dropped", "shares", "removals", "removals_applied")
    }
    totals["controls"] = len(controls)
    totals["controls_approved_in_period"] = sum(1 for control in controls if control["state"] == CONTROL_APPROVED)
    totals["controls_carried"] = sum(1 for control in controls if control["state"] == CONTROL_CARRIED)
    ended = {}
    for control in controls:
        if control["state"] == CONTROL_ENDED:
            ended.setdefault(control["ended_how"], []).append(control)
    totals["controls_ended"] = sorted(ended.items())
    totals["folders"] = sum(len(control["folders"]) for control in controls)
    totals["removals_failed"] = sum(1 for row in tables["removals"] if row["_state"] == "failed")
    totals["removals_recorded"] = sum(1 for row in tables["removals"] if row["_confirmable"])
    totals["removals_confirmable"] = sum(
        1 for row in tables["removals"] if row["_confirmable"] and row["_state"] == "applied"
    )
    totals["removals_confirmed"] = sum(1 for row in tables["removals"] if row["_confirmed"])
    totals["removals_pending"] = sum(1 for row in tables["removals"] if row["_state"] in PENDING_STATES)
    totals["removals_other"] = (
        totals["removals"] - totals["removals_applied"] - totals["removals_failed"] - totals["removals_pending"]
    )
    totals["decisions"] = totals["members"] + totals["shares"] + totals["removals"]
    totals["account_types_known"] = sum(1 for row in tables["members"] if row["_has_account_type"])
    account_types = {}
    for row in tables["members"]:
        if row["_has_account_type"]:
            account_types[row["account_type"]] = account_types.get(row["account_type"], 0) + 1
    totals["account_types"] = dict(sorted(account_types.items()))
    in_period = sorted(
        parse_time(row["_at"]) for row in tables["approvals"] if not row["_carried"] and not row["_ended_on"]
    )
    totals["first_approval"] = in_period[0].strftime("%Y-%m-%d") if in_period else ""
    totals["last_approval"] = in_period[-1].strftime("%Y-%m-%d") if in_period else ""
    approvers = {row["approved_by"] for row in tables["approvals"] if not row["_carried"]}
    totals["approvers"] = len(approvers)
    totals["people_deciding"] = len(
        {row["decided_by"] for row in tables["members"] if not row["_decided_by_policy"]} | approvers
    )
    return totals
