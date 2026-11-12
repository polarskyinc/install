"""Write a Polar Sky access review audit trail (a Markdown table and audit-trail.csv) from saved get_access_review_audit_trail responses.

Python 3 standard library only. Reads no network and no clock, so the same responses give the same bytes.
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

TOOL_AUDIT_TRAIL = "get_access_review_audit_trail"

MAXIMUM_DAYS_PER_CALL = 366

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")

SURFACE_LABELS = {"console": "Polar Sky console", "connector": "AI assistant"}

RESULT_LABELS = {
    "removed": "Removed",
    "failed": "Failed",
    "pending": "Pending",
    "applied": "Applied",
}

ROLE_LABELS = {
    "reader": "Viewer", "writer": "Editor", "commenter": "Commenter", "owner": "Owner", "read": "Read", "write": "Edit",
}

NOT_RECORDED = "Not recorded"

CSV_COLUMNS = (
    "when",
    "control",
    "folders",
    "what_changed",
    "details",
    "made_by",
    "made_through",
    "approved_by",
    "approved_at",
    "result",
    "reason",
    "confirmed_at",
    "change_reference",
    "before",
    "after",
    "source",
    "control_id",
)

MARKDOWN_COLUMNS = (
    ("when", "When"),
    ("control", "Control"),
    ("what_changed", "What changed"),
    ("details", "Details"),
    ("made_by", "Made by"),
    ("approved_by", "Approved by"),
    ("result", "Result"),
    ("confirmed_at", "Confirmed at"),
)

REFUSAL_EXPLANATIONS = {
    "administrator_required": (
        "The audit trail is only for Polar Sky administrators and named control reviewers. A person a control was "
        "only delegated to cannot read it. An administrator can add you as a reviewer."
    ),
    "insufficient_scope": "Reconnect the Polar Sky Controls connector and allow the controls.review scope.",
}


class AuditTrailDataError(ValueError):
    """Raised when the saved responses are refused, incomplete or do not match the requested date range."""


def load_responses(path):
    """Read a folder of saved responses (responses/*.json, in file name order) or one JSON file with a responses list."""
    if os.path.isdir(path):
        responses_directory = os.path.join(path, "responses")
        if not os.path.isdir(responses_directory):
            raise AuditTrailDataError(f"{path} has no responses folder.")
        responses = []
        for name in sorted(os.listdir(responses_directory)):
            if name.endswith(".json"):
                with open(os.path.join(responses_directory, name), encoding="utf-8") as handle:
                    responses.append(json.load(handle))
        return responses
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("responses", [])


def parse_time(value):
    """Parse an RFC 3339 time as Go writes it, nanoseconds included, into an aware UTC datetime."""
    text = str(value).strip().replace("Z", "+00:00")
    match = re.match(r"^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", text)
    if match:
        fraction = "." + match.group(2)[1:7].ljust(6, "0") if match.group(2) else ""
        text = match.group(1) + fraction + match.group(3)
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_time(value):
    """Format a time as YYYY-MM-DD HH:MM:SS UTC, or an empty string."""
    if not value:
        return ""
    return parse_time(value).strftime("%Y-%m-%d %H:%M:%S UTC")


def parse_day(value, label):
    """Parse a YYYY-MM-DD day, naming the argument when it is not one."""
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise AuditTrailDataError(f"{label} must be a day as YYYY-MM-DD, not {value!r}.") from None


def csv_cell(value):
    """Prefix a single quote to a cell a spreadsheet would read as a formula (OWASP CSV injection guidance)."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_TRIGGERS) else text


def markdown_cell(value):
    """Put a value in one Markdown table cell: one line, with the characters Markdown reads as formatting escaped."""
    text = " ".join(("" if value is None else str(value)).split())
    return MARKDOWN_SPECIAL.sub(r"\\\1", text)


def _refusal_message(entry):
    response = entry.get("response") or {}
    reason = response.get("reason") or "refused"
    explanation = REFUSAL_EXPLANATIONS.get(reason, response.get("message") or "")
    return f"{TOOL_AUDIT_TRAIL} was refused ({reason}). {explanation}".strip()


def _series_key(entry):
    arguments = entry.get("arguments") or {}
    response = entry.get("response") or {}
    return (
        arguments.get("from") or response.get("from"),
        arguments.get("to") or response.get("to"),
        arguments.get("control_id") or response.get("control_id") or None,
    )


def collect_series(responses):
    """Group the saved audit trail pages by date range and control, each keyed by the cursor it was called with, and stop on a refused call that was not retried."""
    series = {}
    refusals = []
    for entry in responses:
        if entry.get("tool") != TOOL_AUDIT_TRAIL:
            continue
        cursor = (entry.get("arguments") or {}).get("cursor") or None
        if (entry.get("response") or {}).get("refused"):
            refusals.append((_series_key(entry), cursor, entry))
            continue
        pages = series.setdefault(_series_key(entry), {})
        if cursor in pages and pages[cursor] != entry["response"]:
            raise AuditTrailDataError(f"Two different pages of {TOOL_AUDIT_TRAIL} were saved for the same cursor.")
        pages[cursor] = entry["response"]
    for key, cursor, entry in refusals:
        if cursor not in series.get(key, {}):
            raise AuditTrailDataError(_refusal_message(entry))
    if not series:
        raise AuditTrailDataError(f"The data holds no {TOOL_AUDIT_TRAIL} response.")
    return series


def _walk_pages(pages, label):
    cursor = None
    seen = set()
    walked = []
    while True:
        if cursor not in pages:
            which = "first page" if cursor is None else f"page at cursor {cursor}"
            raise AuditTrailDataError(
                f"{label} is missing its {which}. Fetch every page, with cursor set to next_cursor, until "
                "next_cursor is null."
            )
        if cursor in seen:
            raise AuditTrailDataError(f"{label} repeats the page at cursor {cursor}.")
        seen.add(cursor)
        page = pages[cursor]
        walked.append(page)
        cursor = page.get("next_cursor")
        if cursor is None:
            return walked


def _check_period_covered(series, first_day, last_day, control_id):
    covered = []
    for start, end, series_control_id in series:
        label = f"{TOOL_AUDIT_TRAIL} for {start} to {end}"
        if series_control_id != control_id:
            wanted = f"control {control_id}" if control_id else "every control"
            raise AuditTrailDataError(f"{label} was called for {series_control_id or 'every control'}, not {wanted}.")
        start_day = parse_day(start, f"from of {label}")
        end_day = parse_day(end, f"to of {label}")
        if start_day < first_day or end_day > last_day:
            raise AuditTrailDataError(
                f"{label} reaches outside the requested range {first_day} to {last_day}. Call it only for days inside it."
            )
        covered.append((start_day, end_day))
    covered_until = first_day
    for start_day, end_day in sorted(covered):
        if start_day <= covered_until <= end_day:
            covered_until = end_day + timedelta(days=1)
    if covered_until <= last_day:
        raise AuditTrailDataError(
            f"No {TOOL_AUDIT_TRAIL} response covers {covered_until} to {last_day}. Call it for every part of the range, "
            f"{MAXIMUM_DAYS_PER_CALL} days or less at a time."
        )


def collect_entries(responses, first_day, last_day, control_id=None):
    """Return every change in the requested range once, oldest first, after checking every page was saved."""
    if last_day < first_day:
        raise AuditTrailDataError(f"The last day {last_day} is before the first day {first_day}.")
    series = collect_series(responses)
    _check_period_covered(series, first_day, last_day, control_id)
    seen = set()
    entries = []
    for key in sorted(series, key=lambda item: (item[0], item[1])):
        for page in _walk_pages(series[key], f"{TOOL_AUDIT_TRAIL} for {key[0]} to {key[1]}"):
            for entry in page.get("entries") or []:
                identity = json.dumps(entry, sort_keys=True)
                if identity not in seen:
                    seen.add(identity)
                    entries.append(entry)
    return sorted(entries, key=lambda entry: parse_time(entry.get("at")) if entry.get("at") else datetime.min.replace(tzinfo=timezone.utc))


def _actor_name(actor):
    if not actor:
        return ""
    if actor.get("type") == "system":
        return "Polar Sky"
    return actor.get("name") or "an unknown account"


def _actor_surface(actor):
    if not actor or actor.get("type") == "system":
        return ""
    surface = SURFACE_LABELS.get(actor.get("surface") or "", actor.get("surface") or "")
    client = actor.get("assistant_client")
    return f"{surface} ({client})" if surface and client else surface


def _join(values, separator="; "):
    return separator.join(str(value) for value in values if value not in (None, ""))


def _details(entry):
    if entry.get("step"):
        return entry["step"]
    source = entry.get("source")
    if source == "event":
        roles = ""
        if entry.get("from_role") or entry.get("to_role"):
            roles = f"{_role(entry.get('from_role'))} to {_role(entry.get('to_role'))}"
        return _join([entry.get("person_name"), roles], ", ")
    if source == "removal_record":
        principal = entry.get("principal") or ""
        if entry.get("email") and entry.get("email") != principal:
            principal = f"{principal} ({entry['email']})" if principal else entry["email"]
        target = f"on {entry['target']}" if entry.get("target") else ""
        scope = entry.get("link_scope") or ""
        link_scope = f"link scope {scope}" if scope and scope.lower() not in principal.lower() else ""
        text = _join([principal, _removed_access(entry), target, link_scope], ", ")
        return text[:1].upper() + text[1:]
    return _join([entry.get("principal"), entry.get("target")], ", ")


def _role(value):
    return ROLE_LABELS.get(value, value) if value else "no role"


def _lowered(entry):
    return bool(entry.get("from_role") and entry.get("to_role"))


def _removed_access(entry):
    """Name the access a removal record took away, or the access a lowering went from and to."""
    if _lowered(entry):
        return f"{_role(entry['from_role'])} to {_role(entry['to_role'])}"
    return f"{_role(entry['role'])} access" if entry.get("role") else ""


def _result(entry):
    source = entry.get("source")
    if source == "removal_record":
        value = entry.get("result") or ""
        if value == "removed" and _lowered(entry):
            return "Lowered"
    elif source == "plan":
        value = entry.get("state") or ""
    else:
        return ""
    return RESULT_LABELS.get(value, value.replace("_", " ").capitalize())


def _access_state(entry, key):
    if entry.get("source") != "plan" or entry.get(key) is None:
        return ""
    return json.dumps(entry[key], sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_row(entry):
    """Turn one audit trail entry into the row the table and the CSV file show."""
    source = entry.get("source") or ""
    approval = entry.get("approved_by")
    if source == "event":
        approved_by, approved_at = "", ""
    elif approval:
        approved_by, approved_at = _actor_name(approval), format_time(approval.get("at"))
    else:
        approved_by, approved_at = NOT_RECORDED, ""
    return {
        "when": format_time(entry.get("at")),
        "control": entry.get("control") or "",
        "folders": _join(entry.get("folders") or []),
        "what_changed": entry.get("change") or "",
        "details": _details(entry),
        "made_by": _actor_name(entry.get("actor")),
        "made_through": _actor_surface(entry.get("actor")),
        "approved_by": approved_by,
        "approved_at": approved_at,
        "result": _result(entry),
        "reason": entry.get("reason") or "",
        "confirmed_at": format_time(entry.get("confirmed_at")),
        "change_reference": entry.get("change_reference") or "",
        "before": _access_state(entry, "before"),
        "after": _access_state(entry, "after"),
        "source": source,
        "control_id": entry.get("control_id") or "",
    }


def render_csv(rows):
    """Write the rows as RFC 4180 CSV text with the column ids as the header."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([csv_cell(row[column]) for column in CSV_COLUMNS])
    return buffer.getvalue()


def render_markdown(rows, first_day, last_day, control_id):
    """Write the heading, the counts and the table to show in the chat."""
    scope = "every control"
    if control_id:
        names = sorted({row["control"] for row in rows if row["control"]})
        scope = f"control {markdown_cell(names[0])}" if len(names) == 1 else f"control {control_id}"
    lines = [f"## Audit trail, {first_day} to {last_day} (UTC), {scope}", ""]
    if not rows:
        lines.append("Polar Sky recorded no changes in this range.")
        return "\n".join(lines) + "\n"
    results = {}
    for row in rows:
        if row["result"]:
            results[row["result"]] = results.get(row["result"], 0) + 1
    counted = _join([f"{label} {count}" for label, count in sorted(results.items())], ", ")
    noun = "change" if len(rows) == 1 else "changes"
    lines.append(f"{len(rows)} {noun}, oldest first." + (f" Removals and plan actions: {counted}." if counted else ""))
    lines.append("")
    lines.append("| " + " | ".join(title for _, title in MARKDOWN_COLUMNS) + " |")
    lines.append("|" + "---|" * len(MARKDOWN_COLUMNS))
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(row[column]) for column, _ in MARKDOWN_COLUMNS) + " |")
    return "\n".join(lines) + "\n"


def render(responses, first_day, last_day, control_id=None):
    """Return the output files, name to text, for the saved responses and the requested range."""
    first = parse_day(first_day, "--from")
    last = parse_day(last_day, "--to")
    rows = [entry_row(entry) for entry in collect_entries(responses, first, last, control_id or None)]
    return {
        "audit-trail.csv": render_csv(rows),
        "audit-trail.md": render_markdown(rows, first, last, control_id or None),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True, help="A folder with responses/*.json, or one JSON file with a responses list")
    parser.add_argument("--from", dest="first_day", required=True, help="First day of the range, YYYY-MM-DD")
    parser.add_argument("--to", dest="last_day", required=True, help="Last day of the range, YYYY-MM-DD")
    parser.add_argument("--control-id", default=None, help="The control the trail was read for, if only one")
    parser.add_argument("--out", required=True, help="Output folder")
    arguments = parser.parse_args(argv)
    try:
        files = render(load_responses(arguments.data), arguments.first_day, arguments.last_day, arguments.control_id)
    except AuditTrailDataError as error:
        print(f"Cannot render the audit trail: {error}", file=sys.stderr)
        return 2
    os.makedirs(arguments.out, exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(arguments.out, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    sys.stdout.write(files["audit-trail.md"])
    print()
    for name in sorted(files):
        print(os.path.join(arguments.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
