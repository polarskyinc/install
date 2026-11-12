"""Render the access review report as HTML and CSV files from a report data file.

Usage: python3 render_report.py --data report-data.json --out OUTPUT_FOLDER
"""

import argparse
import csv
import hashlib
import html
import io
import os
import re
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import report_data  # noqa: E402

ASSETS_DIRECTORY = os.path.join(report_data.SKILL_DIRECTORY, "assets")
NOT_AVAILABLE = "Not available in this version"
PATH_COLUMNS = frozenset({"folders", "folder", "target", "item", "email", "group_email", "principal_email"})
PATH_BREAK_POINTS = re.compile(r"(?<=@)|(?=[./-])")
TABLE_ORDER = ("members", "groups", "shares", "removals", "approvals")
EXTRACT_TABLE = "extract"
PDF_FILE = "report.pdf"
WIDE_TABLE_COLUMNS = 8
WIDEST_TABLE_COLUMNS = 12
BAR_COLORS = ("#380081", "#00B2E2", "#BEDEF0", "#4A4A4E")
SECTIONS = (
    "Executive summary", "Scope and method", "Review population", "Why people have access", "Review results",
    "Access removed", "Exceptions", "Sign-off and management acknowledgment", "Attachments",
)


CHANGES_COUNTED = (
    "Changes in period counts the same events as the Polar Sky audit trail: access approved, approval withdrawn "
    "or replaced by a later approval, member added or removed, permission changed, made owner, group kept or "
    "dropped, and approved changes carried out in full or in part. Polar Sky proposing access, or sending a proposal "
    "for review, is not counted. Removals have their own column."
)

OTHER_SYSTEMS = "Other systems in scope for the requirement are reviewed separately."

SITES_INCOMPLETE = (
    "The list may be incomplete: Polar Sky lists the first 25 folders of a folder set, and a folder set has more."
)


def escape(value):
    """Escape a value for HTML text and attributes."""
    return html.escape("" if value is None else str(value), quote=True)


def breakable(value):
    """Escape an email or path for HTML with line-break points after "@" and before ".", "-" and "/"."""
    pieces = PATH_BREAK_POINTS.split("" if value is None else str(value))
    return "<wbr>".join(escape(piece) for piece in pieces if piece)


def number(value):
    """Format a count with thousands separators."""
    return f"{value:,}"


def counted(value, singular, plural):
    """Format a count with the noun that agrees with it."""
    return f"{number(value)} {singular if value == 1 else plural}"


def tbd():
    """Mark a field whose answer is still open."""
    return '<span class="tbd">TBD</span>'


def no_folder_sets(model):
    """Say whether Polar Sky recorded no folder set with an approval in force in the period, so there was no access to review."""
    return not model["totals"]["controls"]


def no_access_to_review(model):
    """The one statement an empty report makes: no folder set had an approval in force, so there was no access to review."""
    return (
        f"Polar Sky recorded no folder sets with an access approval in force from {model['period']['from']} to "
        f"{model['period']['to']}, so there was no access to review."
    )


def rescan_confirmation(totals):
    """Say how many applied removals Polar Sky's read after the removal confirmed, out of the applied ones it records."""
    if not totals["removals_recorded"]:
        return NOT_AVAILABLE.lower()
    return (
        f"{number(totals['removals_confirmed'])} of {number(totals['removals_confirmable'])} applied removals "
        "confirmed by the read after the removal"
    )


DEADLINE_NAMES_SHOWN = 5


def _deadline_names(rows):
    """Name removals with their days, the first few only, pointing to Attachment D for the rest."""
    names = [
        f"{row['principal'] or 'an unnamed grant'} on {row['target']}, {report_data.days_text(row['_days'])}"
        if row["target"] else f"{row['principal'] or 'an unnamed grant'}, {report_data.days_text(row['_days'])}"
        for row in sorted(rows, key=lambda row: (-row["_days"], row["_at"]))
    ]
    shown = names[:DEADLINE_NAMES_SHOWN]
    if len(names) > DEADLINE_NAMES_SHOWN:
        shown.append(f"and {number(len(names) - DEADLINE_NAMES_SHOWN)} more, listed in Attachment D")
    return "; ".join(shown)


def deadline_check(model, names=True):
    """Say how many recorded removals were done within the removal deadline, or None when there is no deadline in days or no removal record."""
    days = model["deadline_days"]
    totals = model["totals"]
    if days is None or not totals["removals_recorded"]:
        return None
    within = totals["removals_within"]
    over = totals["removals_over"]
    latest_attempts = {}
    for row in sorted(totals["removals_open"], key=lambda row: row["_at"]):
        latest_attempts[row["_same_access"]] = row
    still_open = list(latest_attempts.values())
    applied = len(within) + len(over)
    deadline = counted(days, "day", "days")
    if applied:
        text = f"{number(len(within))} of {counted(applied, 'applied removal', 'applied removals')} within {deadline}"
        if over:
            text += f"; {number(len(over))} over" + (f" ({_deadline_names(over)})" if names else "")
    else:
        text = "No applied removals to check"
    if still_open:
        failed = sum(1 for row in still_open if row["_state"] == "failed")
        pending = len(still_open) - failed
        kinds = " and ".join(part for part in (
            f"{number(failed)} failed" if failed else "", f"{number(pending)} pending" if pending else "",
        ) if part)
        low = min(row["_days"] for row in still_open)
        high = max(row["_days"] for row in still_open)
        since = report_data.days_text(low) if low == high else f"{number(low)} to {report_data.days_text(high)}"
        text += f". {kinds} {'removal' if len(still_open) == 1 else 'removals'} not done by the period end, {since} since the decision"
    if totals["removals_no_decision"]:
        text += (
            f". {counted(len(totals['removals_no_decision']), 'removal has', 'removals have')} no approval of its folder set "
            "recorded before it, so it is not checked"
        )
    return text


def approved_by_polar_sky_only(totals):
    """Say which folder sets had no approval by a person in force at the period end, how that came about, and each one's data owner, or nothing."""
    controls = totals["controls_without_person"]
    if not controls:
        return ""
    names = "; ".join(
        f"{control['name']} ("
        + (f"approval {control['ended_how']} {control['ended_on']}" if control["ended_on"] else "approved by Polar Sky")
        + (f"; data owner {control['owner']})" if control["owner"] else "; no data owner recorded)")
        for control in controls
    )
    return (
        f"{counted(len(controls), 'folder set had', 'folder sets had')} no approval by a person in force at the end of "
        f"the period: {names}."
    )


def interval_findings(model):
    """Say when the review period is longer than the review interval, and which folder sets a person last approved too long ago."""
    check = model["interval"]
    if check is None or no_folder_sets(model):
        return []
    found = []
    if check["period_longer"]:
        found.append(f"The review period is longer than the review interval of {check['text']}.")
    if check["stale"]:
        names = "; ".join(
            f"{control['name']} (" + (
                f"last approved by a person {control['last_person_approval'].strftime('%Y-%m-%d')})"
                if control["last_person_approval"] else "no approval by a person in force at the period end)"
            )
            for control in check["stale"]
        )
        found.append(
            f"{counted(len(check['stale']), 'folder set has', 'folder sets have')} no approval by a person from "
            f"{check['cutoff']} on, within {check['text']} of the period end: {names}."
        )
    else:
        found.append(f"Every folder set was approved by a person within {check['text']} of the period end.")
    return found


def checks_before_rendering(model):
    """The points to raise with the person before the report is rendered: folder sets no person approved, the review interval, and a missing acknowledgment title or date."""
    totals = model["totals"]
    points = []
    if totals["controls_without_person"]:
        points.append(
            f"{counted(len(totals['controls_without_person']), 'folder set has', 'folder sets have')} no approval by a "
            "person in force at the end of the period: "
            + "; ".join(control["name"] for control in totals["controls_without_person"]) + "."
        )
    points += [finding for finding in interval_findings(model) if not finding.startswith("Every folder set")]
    acknowledgment = model["acknowledgment"]
    missing = [label for key, label in (("name", "name"), ("title", "title"), ("date", "date")) if not acknowledgment.get(key)]
    if missing:
        points.append(f"The management acknowledgment has no {' and no '.join(missing)}; the report will show TBD.")
    return points


def ended_controls(totals):
    """Say which folder sets were approved and whose approval stopped in the period, grouped by how, such as withdrawn."""
    return " ".join(
        f"{counted(len(controls), 'folder set', 'folder sets')} approved, then {how}: "
        + "; ".join(f"{control['name']}, {report_data.approval_text(control).lower()}" for control in controls)
        + "."
        for how, controls in totals["controls_ended"]
    )


def kept_until_ended(totals):
    """Say how many members kept access only while their folder set's approval was in force, or nothing when none did."""
    if not totals["kept_until_ended"]:
        return ""
    hows = " or ".join(how for how, _ in totals["controls_ended"])
    return (
        f"{number(totals['kept_until_ended'])} of them had their access approved only until their folder set's "
        f"approval was {hows}"
    )


def not_available(text=NOT_AVAILABLE):
    """Mark a section or field the current Polar Sky tools do not supply."""
    return f'<span class="na">{escape(text)}</span>'


def value_or_tbd(value):
    """Escape a customer input, or show TBD when it was not given."""
    return escape(value) if value not in (None, "") else tbd()


def optional_row(key, value):
    """A key and value row for an optional input, or no row when the person did not give it."""
    return [] if value in (None, "") else [(key, escape(value))]


def fill(text, values):
    """Replace {name} placeholders in a framework text."""
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def selected_columns(model, table):
    """Return the columns chosen for a table, in the chosen order, or the defaults."""
    definitions = report_data.load_reference("columns.json")[table]["columns"]
    by_id = {column["id"]: column for column in definitions}
    chosen = (model["inputs"].get("columns") or {}).get(table)
    if chosen is None:
        return [column for column in definitions if column["default"]]
    unknown = [column_id for column_id in chosen if column_id not in by_id]
    if unknown:
        raise report_data.ReportDataError(f"Unknown {table} columns: {', '.join(unknown)}.")
    return [by_id[column_id] for column_id in chosen]


FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value):
    """Prefix a single quote to a cell a spreadsheet would read as a formula (OWASP CSV injection guidance)."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_TRIGGERS) else text


def render_csv(columns, rows):
    """Write rows as RFC 4180 CSV text with the columns' ids as the header."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([column["id"] for column in columns])
    for row in rows:
        writer.writerow([csv_cell(row.get(column["id"], "")) for column in columns])
    return buffer.getvalue()


def key_values(rows):
    """Render a two-column key and value table; values are already HTML."""
    body = "".join(f"<tr><td>{escape(key)}</td><td>{value}</td></tr>" for key, value in rows)
    return f'<table class="ps-table kv"><tbody>{body}</tbody></table>'


def data_table(columns, rows, numeric=(), css_class=""):
    """Render a table of rows under the given columns, right-aligning the numeric ones."""
    head = "".join(
        f'<th class="n">{escape(column["header"])}</th>' if column["id"] in numeric else f"<th>{escape(column['header'])}</th>"
        for column in columns
    )
    body = ""
    for row in rows:
        cells = ""
        for column in columns:
            css = ' class="n"' if column["id"] in numeric else (' class="d"' if column["id"].endswith(("_on", "_at")) else "")
            raw = row.get(column["id"], "")
            text = raw if column.get("html") else escape(raw)
            if not css and column["id"] in PATH_COLUMNS:
                css = ' class="p"'
                text = raw if column.get("html") else breakable(raw)
            cells += f"<td{css}>{text}</td>"
        body += f'<tr{row.get("_row_attributes", "")}>{cells}</tr>'
    wide = "wide" if len(columns) > WIDE_TABLE_COLUMNS else ""
    if len(columns) > WIDEST_TABLE_COLUMNS:
        wide += " widest"
    classes = " ".join(part for part in ("ps-table", css_class, "num" if numeric else "", wide) if part)
    return f'<table class="{classes}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def section_heading(index, title, first_on_page=True):
    """Open a numbered report section."""
    attributes = ' class="page"' if first_on_page else ' style="margin-top:30pt"'
    return f'<section{attributes}>\n  <p class="eyebrow" id="s{index}">Section {index}</p>\n  <h2>{escape(title)}</h2>\n'


def fill_values(model):
    """The values framework texts may refer to."""
    return {
        "organization": model["inputs"]["organization"],
        "provider": model["provider_label"],
        "provider_scope": model["provider_scope"],
        "period_to": model["period"]["to"],
    }


def render_cover(model):
    framework = model["framework"]
    inputs = model["inputs"]
    values = fill_values(model)
    with open(os.path.join(ASSETS_DIRECTORY, "wordmark.svg"), encoding="utf-8") as handle:
        wordmark = handle.read().strip()
    meta = [
        ("Organization", escape(inputs["organization"])),
        ("Report ID", escape(inputs["report_id"])),
        ("Review period", escape(f"{model['period']['from']} to {model['period']['to']}")),
        ("Issued", escape(report_data.format_date(model["issued_at"]))),
        ("Prepared for", escape(inputs.get("prepared_for") or fill(framework["prepared_for"], values))),
        ("Requested by", value_or_tbd(inputs.get("requested_by"))),
    ]
    meta_html = "".join(f"<dt>{escape(key)}</dt><dd>{value}</dd>" for key, value in meta)
    logo = ""
    if model["logo"]:
        logo = f'    <img class="customer-logo" src="{escape(model["logo"])}" alt="{escape(inputs["organization"])} logo">\n'
    return (
        '<section class="cover">\n'
        '  <div class="cover-top">\n'
        f"{logo}"
        f"    {wordmark}\n"
        "  </div>\n"
        '  <div class="cover-title">\n'
        f'    <p class="eyebrow">{escape(framework["eyebrow"])}</p>\n'
        f'    <h1>{escape(framework["title"])}</h1>\n'
        f'    <p class="sub">{escape(fill(framework["subtitle"], values))}</p>\n'
        f'    <dl class="cover-meta">{meta_html}</dl>\n'
        "  </div>\n"
        '  <div class="cover-foot">\n'
        f'    <p>{escape(fill(framework["confidentiality"], values))}</p>\n'
        '    <span class="conf">Confidential</span>\n'
        "  </div>\n"
        "</section>\n"
    )


def render_contents(model):
    inputs = model["inputs"]
    acknowledgment = model["acknowledgment"]
    toc = "".join(
        f'<li><a href="#s{index}"><span>{index}</span>{escape(title)}</a></li>'
        for index, title in enumerate(SECTIONS, start=1)
    )
    data_source = inputs.get("data_source") or f"{model['provider_label'][:1].upper()}{model['provider_label'][1:]}, read by Polar Sky"
    acknowledged = tbd()
    if acknowledgment.get("name"):
        acknowledged = escape(
            f"{report_data.format_date(acknowledgment.get('date')) or 'Date TBD'} by {acknowledgment['name']}"
            + (f", {acknowledgment['title']}" if acknowledgment.get("title") else "")
        )
    rows = [("Requirement", escape(model["framework"]["control"]))]
    rows += optional_row("Review owner", inputs.get("control_owner"))
    rows += [
        ("Review procedure", value_or_tbd(inputs.get("procedure"))),
        ("Removal deadline", value_or_tbd(inputs.get("removal_deadline"))),
        ("Retention", value_or_tbd(inputs.get("retention"))),
    ]
    if inputs.get("review_interval") or model["framework_key"] in ("soc2", "sox"):
        rows.append(("Review interval", value_or_tbd(inputs.get("review_interval"))))
    rows += optional_row("Previous review", inputs.get("previous_review"))
    rows += [
        ("Data source", escape(data_source)),
        ("Generated", escape(
            f"{report_data.format_time(inputs['generated_at'])} by the Polar Sky compliance report skill. "
            "The skill's renderer computed every count and hash from Polar Sky records."
        )),
        ("Acknowledged", acknowledged),
        ("Issued", escape(report_data.format_time(model["issued_at"]))),
    ]
    return (
        '<section class="page">\n  <h2>Contents</h2>\n'
        f'  <ol class="toc">{toc}</ol>\n'
        '  <h2 style="margin-top:30pt">Report details</h2>\n'
        f"  {key_values(rows)}\n</section>\n"
    )


def checklist_evidence(model, key):
    totals = model["totals"]
    inputs = model["inputs"]
    acknowledgment = model["acknowledgment"]
    approved = (
        f"Access to {number(totals['controls_approved_in_period'])} of "
        f"{counted(totals['controls'], 'folder set', 'folder sets')} reviewed and approved"
    ) if totals["controls"] else "No folder sets to review"
    if totals["first_approval"]:
        approved += f" {totals['first_approval']} to {totals['last_approval']}"
    approved += "."
    by_polar_sky = sum(1 for control in model["controls"] if control["last_approval_by_polar_sky"])
    if by_polar_sky:
        approved += f" {number(by_polar_sky)} of them {'was' if by_polar_sky == 1 else 'were'} approved by Polar Sky itself, not by a person."
    if totals["controls_ended"]:
        approved += " " + ended_controls(totals)
    if totals["controls_carried"]:
        approved += f" {number(totals['controls_carried'])} approved before the period, still in force."
    if key == "approvals":
        previous = inputs.get("previous_review")
        return (f"Previous review: {previous}. " if previous else "Previous review not recorded. ") + approved
    if key == "interval":
        interval = inputs.get("review_interval") or "TBD"
        text = f"Interval set by the company: {interval}. Review period {model['period']['from']} to {model['period']['to']}. " + approved
        checked = interval_findings(model)
        return text + (" " + " ".join(checked) if checked else "")
    if key == "decisions":
        if not totals["members"] and not totals["shares"]:
            return "No members or kept direct shares."
        text = (
            f"{counted(totals['members'], 'member', 'members')} at report time, as at "
            f"{report_data.format_date(model['members_as_of'])}, each with who decided and when."
        )
        if totals["shares"]:
            text += f" {counted(totals['shares'], 'kept direct share', 'kept direct shares')}, read {report_data.format_date(model['shares_read_at'])}."
        return text
    if key == "who_decided":
        if not totals["members"]:
            return "No members."
        text = (
            f"{number(totals['kept_by_policy'])} proposed by Polar Sky. "
            f"{number(totals['kept_by_person'])} added or changed by a person."
        )
        if totals["kept_until_ended"]:
            text += f" {kept_until_ended(totals)}."
        if totals["keeps_nothing"]:
            text += f" {number(totals['keeps_nothing'])} keep nothing."
        if totals["controls_without_person"]:
            text += " " + approved_by_polar_sky_only(totals)
        return text
    if key == "account_types":
        return account_types_evidence(model)
    if key == "removals":
        if not totals["removals"]:
            return "No removals."
        text = (
            f"{number(totals['removals_applied'])} applied, {number(totals['removals_failed'])} failed, "
            f"{number(totals['removals_pending'])} pending, {number(totals['removals_other'])} not applied. Re-scan confirmation: {rescan_confirmation(totals)}."
        )
        within = deadline_check(model, names=False)
        return text + (f" Within the deadline: {within}." if within else "")
    if key == "acknowledgment":
        if not acknowledgment.get("name"):
            return "TBD"
        who = ", ".join(part for part in (acknowledgment["name"], acknowledgment.get("title")) if part)
        return f"{who}, {report_data.format_date(acknowledgment.get('date')) or 'date TBD'}."
    if key == "sites":
        if model["sites"] and not model["sites_complete"]:
            return f"At least {number(len(model['sites']))} sites, listed in Section 3. {SITES_INCOMPLETE}"
        if model["sites"]:
            return f"{number(len(model['sites']))} sites, listed in Section 3."
        if not totals["folders"]:
            return "No folders."
        return f"{number(totals['folders'])} folders, listed in Attachment A."
    raise report_data.ReportDataError(f"Unknown checklist evidence {key!r}.")


def account_type_counts(totals):
    """Count members by account type, with those whose type is not recorded last, such as "Full time 4, not recorded 4"."""
    parts = [f"{name} {number(count)}" for name, count in totals["account_types"].items()]
    unknown = totals["members"] - totals["account_types_known"]
    if unknown:
        parts.append(f"not recorded {number(unknown)}")
    return ", ".join(parts)


def account_types_evidence(model):
    """Say which account types the provider gives for the members, and where the guest accounts are listed with who decided their access."""
    totals = model["totals"]
    if not totals["members"]:
        return "No members."
    if not totals["account_types_known"]:
        return (
            "No account types recorded, so this report does not show which members are guest or vendor accounts. "
            f"Attachment A lists all {counted(totals['members'], 'member', 'members')}"
            f"{attachment_a_details(model, account_type=False)}."
        )
    text = f"Account types: {account_type_counts(totals)}."
    for provider in totals["account_type_providers"]:
        text += " " + provider_account_types(model, provider)
    for provider in totals["providers_without_account_types"]:
        name = report_data.PROVIDER_LABELS.get(provider, ("the provider",))[0]
        text += f" No account types recorded for the {name} members, so the report does not show which of them are guest or vendor accounts."
    return text


def attachment_a_details(model, account_type=True):
    """The words naming what Attachment A shows of each member, by the member columns chosen, such as " with who decided their access and when"."""
    chosen = {column["id"] for column in selected_columns(model, "members")}
    details = []
    if account_type and "account_type" in chosen:
        details.append("their account type")
    if {"decided_by", "decided_on"} <= chosen:
        details.append("who decided their access and when")
    elif "decided_by" in chosen:
        details.append("who decided their access")
    elif "decided_on" in chosen:
        details.append("when their access was decided")
    return " with " + " and ".join(details) if details else ""


def provider_account_types(model, provider):
    """The sentence on one provider's account types: Microsoft 365 guests, or the types another provider gives."""
    totals = model["totals"]
    if provider == report_data.MICROSOFT_365:
        guests = totals["guest_members"]
        if not guests:
            return "Microsoft 365 lists no member as a Guest account."
        accounts = totals["guest_accounts"]
        who = counted(guests, "Guest member", "Guest members")
        if accounts != guests:
            who += f" ({counted(accounts, 'account', 'accounts')})"
        verb = "is" if guests == 1 else "are each"
        if "account_type" not in {column["id"] for column in selected_columns(model, "members")}:
            return (
                "Attachment A lists every member, but its chosen columns leave out the account type, so it does not "
                "show which members are Guest accounts."
            )
        return f"The {who} {verb} listed in Attachment A{attachment_a_details(model, account_type=False)}."
    name = report_data.PROVIDER_LABELS.get(provider, ("the provider",))[0]
    return f"Account types are as {name} gives them; Attachment A lists each member{attachment_a_details(model)}."


def outcome_bar(totals):
    segments = [
        ("Proposed by Polar Sky", totals["kept_by_policy"]),
        ("Added or changed by a person", totals["kept_by_person"]),
        ("Kept direct shares", totals["shares"]),
        ("Removals", totals["removals"]),
    ]
    total = sum(count for _, count in segments)
    if not total:
        return ""
    label = f"Outcome of the {number(total)} access decisions"
    shown = [(name, count, color) for (name, count), color in zip(segments, BAR_COLORS) if count]
    rectangles = ""
    x = 0.0
    available = 640 - 2 * max(len(shown) - 1, 0)
    for name, count, color in shown:
        width = available * count / total
        rectangles += (
            f'<rect x="{x:.1f}" y="0" width="{width:.1f}" height="28" rx="2" fill="{color}">'
            f"<title>{escape(name)}: {number(count)}</title></rect>"
        )
        x += width + 2
    legend = "".join(
        f'<li><span class="key" style="background:{color}"></span>{escape(name)} <b>{number(count)}</b></li>'
        for (name, count), color in zip(segments, BAR_COLORS)
    )
    return (
        f'<figure class="chart"><figcaption>{escape(label)}</figcaption>'
        f'<svg viewBox="0 0 640 28" preserveAspectRatio="none" class="bar-strip" role="img" aria-label="{escape(label)}">'
        f'{rectangles}</svg><ul class="legend">{legend}</ul></figure>'
    )


def section_links(sections):
    """Link to report sections by number."""
    return ", ".join(f'<a class="xref" href="#s{section}">{section}</a>' for section in sections)


def summary_paragraph(model):
    """The paragraph that opens Section 1: what was reviewed and by whom, or that there was no access to review."""
    totals = model["totals"]
    if no_folder_sets(model):
        return no_access_to_review(model) + " A folder set is one folder, or a group of folders, with a data owner."
    text = (
        f"{model['inputs']['organization']} reviewed access to {model['framework']['scope_noun']} in "
        f"{model['provider_label']} from {model['period']['from']} to {model['period']['to']} for "
        f"{counted(totals['controls'], 'folder set', 'folder sets')}. Each folder set is one folder, or a group of folders, "
        "with a data owner. For each folder set, Polar Sky proposed who should keep access and why, and the data owner "
        "or another authorized approver reviewed and approved that access in Polar Sky. "
        f"{counted(totals['people_deciding'], 'person', 'people')} approved access or added or changed it."
    )
    if totals["controls_without_person"]:
        text += " " + approved_by_polar_sky_only(totals)
    if totals["controls_ended"]:
        text += " " + ended_controls(totals)
    return text


def summary_stats(model):
    """The figure cards under the Section 1 paragraph, or nothing when there were no folder sets to count."""
    if no_folder_sets(model):
        return ""
    totals = model["totals"]
    stats = [
        ("Folder sets approved", f"{number(totals['controls_approved_in_period'])} <small>of {number(totals['controls'])}</small>", 5),
        ("Access decisions", number(totals["decisions"]), 3),
        ("Removals", f"{number(totals['removals_applied'])} <small>applied of {number(totals['removals'])}</small>", 6),
        ("Kept direct shares", number(totals["shares"]), 5),
    ]
    cards = "".join(
        f'<a class="stat" href="#s{section}"><span class="k">{escape(key)}</span><span class="v">{value}</span>'
        f'<span class="go">Section {section}</span></a>'
        for key, value, section in stats
    )
    return f'  <div class="stats">{cards}</div>\n'


def render_summary(model):
    framework = model["framework"]
    rows = "".join(
        f"<tr><td>{escape(item['requirement'])}</td><td>{escape(checklist_evidence(model, item['evidence']))}</td>"
        f"<td>{section_links(item['sections'])}</td></tr>"
        for item in framework["checklist"]
    )
    bar = outcome_bar(model["totals"])
    return (
        section_heading(1, SECTIONS[0])
        + f"  <p>{escape(summary_paragraph(model))}</p>\n"
        + summary_stats(model)
        + f'  <table class="ps-table checklist"><thead><tr><th>{escape(framework["checklist_heading"])}</th><th>Evidence</th><th>Section</th></tr></thead><tbody>{rows}</tbody></table>\n'
        + (f"  {bar}\n" if bar else "")
        + "</section>\n"
    )


def render_scope(model):
    framework = model["framework"]
    inputs = model["inputs"]
    values = fill_values(model)
    totals = model["totals"]
    provider = model["provider_label"]
    period = f"from {model['period']['from']} to {model['period']['to']}"
    if no_folder_sets(model):
        paragraphs = [
            f"This report documents what Polar Sky recorded about access to {framework['scope_noun']} in {provider} {period}. "
            f"{fill(framework['purpose'], values)}",
            f"<b>Scope.</b> No folder sets. {other_systems(model)}",
            f"<b>Requirement.</b> {framework['requirement']}",
        ]
    else:
        paragraphs = [
            f"This report documents {inputs['organization']}'s review of access to {framework['scope_noun']} in "
            f"{provider} {period}. {fill(framework['purpose'], values)}",
            f"<b>Scope.</b> The {counted(totals['controls'], 'folder set', 'folder sets')} whose access approval was in "
            "force during the period, and the access Polar Sky records for them: every member, every group kept or "
            f"dropped, and every direct share kept. This report covers only these folder sets in {provider}. "
            f"{other_systems(model)}",
            "<b>How the review was done.</b> Access was reviewed as it changed during the period, not in a single campaign "
            "at the end. For each folder set, Polar Sky proposed who should keep access and why, and the data owner or "
            "another authorized approver reviewed and approved that access in Polar Sky. Polar Sky made the "
            f"removals in {provider} and recorded the result of each one.",
            "<b>Who decided.</b> For people Polar Sky proposed, the decision is the approval of their folder set's access "
            "that included them; Attachment A shows anyone proposed after an approval was withdrawn. "
            "A person who added someone or changed their access is named, with the date. Each approval is recorded with "
            "who approved it and when.",
            f"<b>Requirement.</b> {framework['requirement']}",
        ]
    body = f"  <p>{escape(paragraphs[0])}</p>\n" + "".join(f"  <p>{_bold_lead(paragraph)}</p>\n" for paragraph in paragraphs[1:])
    return section_heading(2, SECTIONS[1]) + body + "</section>\n"


def other_systems(model):
    """Say that systems outside these folder sets are reviewed separately, in the framework's words or generic ones."""
    return fill(model["framework"].get("other_systems") or OTHER_SYSTEMS, fill_values(model))


def _bold_lead(paragraph):
    lead, rest = paragraph.split("</b>", 1)
    return f"<b>{escape(lead.removeprefix('<b>'))}</b>{escape(rest)}"


def render_population(model):
    totals = model["totals"]
    inputs = model["inputs"]
    extract = model["extract"]
    folders = f"{number(totals['folders'])} folders"
    if model["sites"]:
        folders += f" on {number(len(model['sites']))} sites"
    members = members_text(model)
    shares = shares_text(model)
    rows = [
        ("Source", escape(f"Polar Sky records of {provider_name(model)}: folder sets, approvals, members, groups, kept direct shares and removals")),
        ("Folder sets", escape(controls_population(totals))),
        ("Folders", escape(folders if totals["folders"] else "No folders")),
    ]
    if model["sites"]:
        sites = "; ".join(model["sites"])
        if not model["sites_complete"]:
            sites += f". {SITES_INCOMPLETE}"
        rows.append(("Sites", escape(sites)))
    rows += [
        ("Groups", escape(groups_text(model))),
        ("Members at report time", escape(members)),
        ("Kept direct shares", escape(shares)),
        ("Access decisions", escape(decisions_text(totals))),
    ]
    rows += extract_rows(extract)
    if model["unlisted"] is not None:
        rows.append(("Not in the members list", escape(unlisted_text(model["unlisted"]))))
    rows += extract_method_rows(extract)
    rows += optional_row("Exclusions", inputs.get("exclusions"))
    return (
        section_heading(3, SECTIONS[2], first_on_page=False)
        + f"  <p>{escape(extract_intro(extract))}</p>\n  {key_values(rows)}\n"
        + extract_tables(extract)
        + unlisted_table(model)
        + "</section>\n"
    )


def groups_text(model):
    """Say how many groups the folder sets kept and dropped."""
    totals = model["totals"]
    if no_folder_sets(model):
        return "No groups"
    text = f"{number(totals['groups_kept'])} kept, {number(totals['groups_dropped'])} dropped"
    if totals["groups_live"]:
        text += f", {number(totals['groups_live'])} more found in the live read and not decided in Polar Sky, listed in Attachment B"
    return text


def members_text(model):
    """Say how many members the folder sets have at report time, who decided them, and when they were read."""
    totals = model["totals"]
    if no_folder_sets(model):
        return "No members"
    text = (
        f"{number(totals['members'])}: {number(totals['kept_by_policy'])} proposed by Polar Sky, "
        f"{number(totals['kept_by_person'])} added or changed by a person"
    )
    if totals["keeps_nothing"]:
        text += f", {number(totals['keeps_nothing'])} keep nothing"
    if totals["kept_until_ended"]:
        text += f". {kept_until_ended(totals)}"
    if totals["account_types_known"]:
        text += ". " + account_type_counts(totals)
    return text + (
        f". Read {report_data.format_time(model['members_as_of'])}, as they are at report time, "
        "not as at the end of the period"
    )


def shares_text(model):
    """Say how many kept direct shares the report lists and when they were read."""
    if no_folder_sets(model):
        return "No kept direct shares"
    text = number(model["totals"]["shares"])
    if model["shares_read_at"]:
        text += (
            f", read {report_data.format_time(model['shares_read_at'])}. Read as they are now, not as at approval; "
            "Polar Sky does not record who decided to keep them or when"
        )
    return text


def decisions_text(totals):
    """Say how many access decisions the report counts and what they are made of."""
    if not totals["controls"]:
        return "No access decisions"
    return (
        f"{number(totals['decisions'])}: {counted(totals['members'], 'member', 'members')}, "
        f"{counted(totals['shares'], 'kept direct share', 'kept direct shares')} and {counted(totals['removals'], 'removal', 'removals')} in the period"
    )


def controls_population(totals):
    """Say how many folder sets the report covers and how their approvals stood in the period."""
    if not totals["controls"]:
        return "No folder sets"
    parts = [f"{number(totals['controls_approved_in_period'])} approved in the period"]
    parts += [f"{number(len(controls))} approved, then {how}" for how, controls in totals["controls_ended"]]
    if totals["controls_carried"]:
        parts.append(f"{number(totals['controls_carried'])} approved before the period, still in force")
    return f"{number(totals['controls'])}: " + "; ".join(parts)


def provider_name(model):
    return model["provider_label"]


EXTRACT_METHODS = {
    "microsoft365": (
        "Polar Sky read each folder's permissions live from Microsoft 365, and listed the members of every Entra group "
        "and SharePoint group they grant, with Microsoft 365's own count of each Entra group"
    ),
    "google_workspace": (
        "Polar Sky read each folder's permissions live from Google Drive, and listed the members of every Google group "
        "they grant, nested groups included, with Google Workspace's own count of each group's direct members"
    ),
}

EXTRACT_METHOD_WITHOUT_PROVIDER = (
    "Polar Sky read each folder's permissions live, and listed the members of every group they grant"
)

GOOGLE_COUNT_METHOD = (
    " For each Google group, Polar Sky compared the direct members it read with Google Workspace's count of direct "
    "members, for the group and every group nested in it. A group matches only when all of them match."
)


def extract_provider(extract):
    """Name the providers the extract read from, as the report names them."""
    return " and ".join(report_data.PROVIDER_LABELS[provider][0] for provider in extract["providers"])


def from_provider(extract):
    """The words naming where the extract read from, such as " from Google Workspace", or nothing when no data names a provider."""
    provider = extract_provider(extract)
    return f" from {provider}" if provider else ""

EXTRACT_LINKS_NOT_LISTED = (
    "The extract lists every link on the folders it read. Sharing links on files and subfolders inside the folders are not listed: the extract reads "
    "the folders' permissions only"
)


def extract_method_rows(extract):
    """The Section 3 rows that say how the extract was built and which links it leaves out, known only from a completed extract."""
    if not completed(extract):
        return [("How the list was built", not_available()), ("Link types not listed", not_available())]
    if read_no_folder(extract):
        why = "3.2 lists what was left out and why" if extract["exclusions"] else "no folder was in scope"
        return [
            ("How the list was built", escape(f"Polar Sky read no folder, so the extract lists no access: {why}")),
            ("Link types not listed", not_available("Not available: no folder was read")),
        ]
    method = "; ".join(EXTRACT_METHODS[provider] for provider in extract["providers"]) or EXTRACT_METHOD_WITHOUT_PROVIDER
    if extract["exclusions"]:
        method += ". 3.2 lists what was left out and why"
    return [("How the list was built", escape(method)), ("Link types not listed", escape(EXTRACT_LINKS_NOT_LISTED))]


def read_no_folder(extract):
    """Say whether a completed extract read no folder at all, so it lists no access."""
    return completed(extract) and extract["folders_read"] == 0


def completed(extract):
    """Say whether the report has a completed extract."""
    return bool(extract) and extract["status"] == report_data.EXTRACT_COMPLETED


def extract_intro(extract):
    """The sentence that opens Section 3, by what became of the extract."""
    text = "The access in scope comes from Polar Sky's records of each folder set. "
    if read_no_folder(extract):
        started = (
            f"Polar Sky started a live read of who has access{from_provider(extract)} at "
            f"{report_data.format_time(extract['as_of'])}, "
        )
        if not extract["exclusions"]:
            return text + started + "but no folder was in scope, so the stored extract is empty."
        return text + started + "but it read no folder, so the stored extract is empty. Section 3.2 lists what was left out and why."
    if completed(extract):
        return text + (
            f"Polar Sky also read who has access live{from_provider(extract)} at "
            f"{report_data.format_time(extract['as_of'])} and stored that read once, as a file that cannot change. "
            "Attachment F names the file and its SHA-256, and holds its rows as a CSV file."
        )
    if extract:
        return text + "Polar Sky started a live read of who has access, but it failed, so this report has no extract."
    return text + "A separate extract of who has access as of one time is not available in this version."


def _kinds(counts):
    return ", ".join(f"{name} {number(count)}" for name, count in counts)


def extract_rows(extract):
    """The Section 3 rows that describe the extract."""
    if not extract:
        return [(key, not_available()) for key in ("Extract taken", "Independent count", "SHA-256 of extract")]
    days = ("Extract days", escape(f"Folder sets with an approval in force {extract['from']} to {extract['to']}")
            if extract["from"] and extract["to"] else not_available("Not recorded"))
    if not completed(extract):
        return [
            ("Extract", escape(f"Failed: {extract['failure_reason'] or 'Polar Sky gave no reason'}")),
            days,
            ("SHA-256 of extract", not_available("Not available: the extract failed")),
        ]
    file = extract["file"]
    stored = ", ".join(part for part in (
        file.get("reference") or "",
        counted(file["bytes"], "byte", "bytes") if isinstance(file.get("bytes"), int) else "",
        file.get("format") or "",
    ) if part)
    verified = {
        True: "Yes. Polar Sky checked the whole stored file against this SHA-256 when its rows were read.",
        False: "No. Polar Sky did not confirm the stored file against this SHA-256 when its rows were read.",
    }.get(extract["sha256_verified"], "Not recorded")
    if not extract["row_hashes_match"]:
        verified += " The row pages name a different SHA-256 than the stored file."
    rows_text = number(extract["rows"])
    if extract["rows_by_kind"]:
        rows_text += f": {_kinds(extract['rows_by_kind'])}"
    rows_text += (
        f". From {counted(extract['controls'] or 0, 'folder set', 'folder sets')} and "
        f"{counted(extract['folders_read'] or 0, 'folder', 'folders')} read"
    )
    if read_no_folder(extract) and not extract["rows"]:
        rows_text = "No rows: Polar Sky read no folder"
    read_text = f"{number(extract['rows_read'])}, all in Attachment F" if extract["rows_read"] else "No rows"
    if not extract["rows_read_match"]:
        read_text = (
            f"{number(extract['rows_read'])}: {_kinds(extract['rows_read_by_kind'])}. "
            "This differs from the extract's own row counts above."
        )
    exclusions = extract["exclusions"]
    return [
        ("Extract taken", escape(report_data.format_time(extract["as_of"]))),
        days,
        ("Extract file", escape(stored)),
        ("SHA-256 of extract", f"<code>{escape(file.get('sha256'))}</code>" if file.get("sha256") else tbd()),
        ("Hash checked", escape(verified)),
        ("Extract rows", escape(rows_text)),
        ("Rows read", escape(read_text)),
        ("Independent count", escape(independent_count(extract))),
        ("Could not be read", escape(could_not_be_read(extract))),
    ]


def could_not_be_read(extract):
    """Say what the extract could not read: the items 3.2 lists, or nothing, and why nothing."""
    exclusions = extract["exclusions"]
    if exclusions:
        return f"{counted(len(exclusions), 'item', 'items')}, listed in 3.2 with the reason"
    if read_no_folder(extract):
        return "Nothing: no folder was in scope"
    return "Nothing: Polar Sky read everything in scope"


def independent_count(extract):
    """Say how Polar Sky's count of each group's members compares with the provider's own count."""
    groups = extract["groups"]
    if not groups:
        return "No groups to count."
    provider = extract_provider(extract) if len(extract["providers"]) == 1 else "its provider"
    matching = sum(1 for group in groups if group["result"] == "Matches")
    text = (
        f"{counted(len(groups), 'group', 'groups')} counted. "
        f"{counted(matching, 'matches', 'match')} {provider}'s own count."
    )
    differ = extract["groups_differ"]
    if differ:
        text += f" {counted(len(differ), 'differs', 'differ')}: " + "; ".join(_group_difference(group) for group in differ) + "."
    if extract["groups_without_provider_count"]:
        text += f" {counted(extract['groups_without_provider_count'], 'has', 'have')} no count from {provider}."
    if any(group["provider"] == "google_workspace" for group in groups):
        text += GOOGLE_COUNT_METHOD
    return text


def _group_difference(group):
    if group["result"] == report_data.NESTED_GROUP_DIFFERS:
        return f"{group['group_name']} (a group nested in it differs or could not be read)"
    return (
        f"{group['group_name']} (Polar Sky counted {number(group['counted_members'])}, "
        f"{group['provider_label']} reports {number(group['provider_member_count'])})"
    )


UNLISTED_MEANING = (
    "The live read found this access to the folders, but the members list in Attachment A does not show it: the person "
    "is not a member of the folder set, or is a member with another permission, often a role on a shared drive or site "
    "that every folder in it inherits. Polar Sky's review of the folder set did not cover this access."
)


def unlisted_text(unlisted):
    """Say how many grants in the live read the members list does not show, and to how many people."""
    if not unlisted:
        return "Nothing: the members list shows every person's access the live read found"
    people = len({row["email"].lower() or row["person_name"].lower() for row in unlisted})
    return f"{counted(len(unlisted), 'grant', 'grants')} to {counted(people, 'person', 'people')}, listed in 3.3"


def unlisted_table(model):
    """Section 3.3: the person grants in the live read that the members list does not show."""
    unlisted = model["unlisted"]
    if unlisted is None:
        return ""
    columns = [
        {"id": "folder_set", "header": "Folder set"}, {"id": "folder", "header": "Folder"},
        {"id": "person_name", "header": "Person"}, {"id": "email", "header": "Email"},
        {"id": "role", "header": "Permission"}, {"id": "inherited", "header": "Inherited"},
        {"id": "why", "header": "Members list"},
    ]
    body = f"  {data_table(columns, unlisted)}\n" if unlisted else f"  <p>{escape(unlisted_text(unlisted))}.</p>\n"
    return f"  <h3>3.3 Access not in the members list</h3>\n  <p>{escape(UNLISTED_MEANING)}</p>\n" + body


def extract_tables(extract):
    """The group count and exclusion tables of a completed extract."""
    if not completed(extract):
        return ""
    group_columns = [
        {"id": "group_name", "header": "Group"},
        {"id": "kind", "header": "Kind"},
        {"id": "counted", "header": "Counted by Polar Sky"},
        {"id": "provider", "header": f"{extract_provider(extract)}'s count" if len(extract["providers"]) == 1 else "Provider's count"},
        {"id": "result", "header": "Result"},
    ]
    group_rows = [
        {
            "group_name": group["group_name"], "kind": group["kind"], "counted": number(group["counted_members"]),
            "provider": "" if group["provider_member_count"] is None else number(group["provider_member_count"]),
            "result": group["result"],
        }
        for group in extract["groups"]
    ]
    exclusion_columns = [
        {"id": "folder_set", "header": "Folder set"},
        {"id": "subject", "header": "Not read"},
        {"id": "reason", "header": "Reason"},
    ]
    return (
        "  <h3>3.1 Group member counts</h3>\n"
        + (f"  {data_table(group_columns, group_rows, numeric=('counted', 'provider'))}\n" if group_rows
           else "  <p>No groups to count.</p>\n")
        + "  <h3>3.2 Could not be read</h3>\n"
        + (f"  {data_table(exclusion_columns, extract['exclusions'])}\n" if extract["exclusions"]
           else f"  <p>{escape(could_not_be_read(extract))}.</p>\n")
    )


def render_policy(model):
    columns = [
        {"id": "name", "header": "Folder set"},
        {"id": "folders_text", "header": "Folders"},
        {"id": "owner", "header": "Data owner"},
        {"id": "reason", "header": "Reason for access"},
        {"id": "kept_by_policy", "header": "Proposed by Polar Sky"},
    ]
    rows = [
        {
            "name": control["name"],
            "folders_text": "; ".join(control["folders"]),
            "owner": control["owner"] or "Not recorded",
            "reason": control["reason"] or control["purpose"] or "Not recorded",
            "kept_by_policy": number(control["counts"]["kept_by_policy"]),
        }
        for control in model["controls"]
    ]
    text = (
        "For each folder set, Polar Sky proposed who should keep access and why, and the data owner or another "
        "authorized approver reviewed and approved it. The reason below applies to the people Polar Sky proposed. "
        "For people a person added or whose access a person changed, Attachment A names who made the change and when."
    )
    note = "Separate access rules with their own approvals: " + NOT_AVAILABLE.lower() + "."
    reasons = f"  <p>{escape(text)}</p>\n  {data_table(columns, rows, numeric=('kept_by_policy',))}\n"
    if no_folder_sets(model):
        reasons = "  <p>No folder sets, so no reasons for access.</p>\n"
    return (
        section_heading(4, SECTIONS[3])
        + reasons
        + f'  <p class="note">{escape(note)}</p>\n</section>\n'
    )


def control_name_cell(control):
    """The by-folder-set name cell: the name, and under it the approval when that approval ended in the period."""
    if control["state"] != report_data.CONTROL_ENDED:
        return escape(control["name"])
    return f'{escape(control["name"])}<br><span class="cell-note">{escape(report_data.approval_text(control))}</span>'


def render_results(model):
    totals = model["totals"]
    by_control_columns = [
        {"id": "name", "header": "Folder set", "html": True},
        {"id": "folders", "header": "Folders"},
        {"id": "groups_kept", "header": "Groups kept"},
        {"id": "members", "header": "Members at report time"},
        {"id": "kept_by_policy", "header": "Proposed by Polar Sky"},
        {"id": "kept_by_person", "header": "Added or changed by a person"},
        {"id": "shares", "header": "Direct shares"},
        {"id": "removals", "header": "Removals"},
        {"id": "activity", "header": "Changes in period"},
    ]
    numeric = tuple(column["id"] for column in by_control_columns[1:])
    rows = []
    for control in model["controls"]:
        counts = control["counts"]
        rows.append({
            "name": control_name_cell(control), "folders": number(len(control["folders"])),
            "groups_kept": number(counts["groups_kept"]), "members": number(counts["members"]),
            "kept_by_policy": number(counts["kept_by_policy"]), "kept_by_person": number(counts["kept_by_person"]),
            "shares": number(counts["shares"]), "removals": number(counts["removals"]),
            "activity": number(control["activity_in_period"]),
        })
    rows.append({
        "name": escape("Total"), "folders": number(totals["folders"]), "groups_kept": number(totals["groups_kept"]),
        "members": number(totals["members"]), "kept_by_policy": number(totals["kept_by_policy"]),
        "kept_by_person": number(totals["kept_by_person"]), "shares": number(totals["shares"]),
        "removals": number(totals["removals"]),
        "activity": number(sum(control["activity_in_period"] for control in model["controls"])),
        "_row_attributes": ' class="total"',
    })
    approvers = {}
    for row in model["tables"]["approvals"]:
        if row["_carried"]:
            continue
        entry = approvers.setdefault(
            (row["approved_by"], row["approver_type"]), {"controls": set(), "dates": [], "owners": set()}
        )
        entry["controls"].add(row["folder_set"])
        entry["dates"].append(report_data.format_date(row["_at"]))
        entry["owners"] |= {control["owner"] for control in model["controls"] if control["name"] == row["folder_set"] and control["owner"]}
    approver_columns = [
        {"id": "approved_by", "header": "Approved by"},
        {"id": "approver_type", "header": "Approver type"},
        {"id": "controls", "header": "Folder sets"},
        {"id": "first", "header": "First approval"},
        {"id": "last", "header": "Last approval"},
    ]
    approver_rows = [
        {
            "approved_by": approver_label(name, kind, entry["owners"]), "approver_type": kind,
            "controls": number(len(entry["controls"])), "first": min(entry["dates"]), "last": max(entry["dates"]),
        }
        for (name, kind), entry in sorted(approvers.items(), key=lambda item: (item[0][1] != report_data.APPROVER_PERSON, item[0][0].lower()))
    ]
    group_columns = selected_columns(model, "groups")
    share_columns = selected_columns(model, "shares")
    if no_folder_sets(model):
        return "".join([
            section_heading(5, SECTIONS[4]),
            "  <h3>5.1 By folder set</h3>\n  <p>No folder sets.</p>\n",
            "  <h3>5.2 Access approvals</h3>\n  <p>No access was approved during the period.</p>\n",
            "  <h3>5.3 Groups</h3>\n  <p>No groups.</p>\n",
            "  <h3>5.4 Kept direct shares</h3>\n  <p>No kept direct shares.</p>\n",
            "  <h3>5.5 Site owners and applications</h3>\n",
            f"  <p>{not_available()}.</p>\n",
            "</section>\n",
        ])
    parts = [
        section_heading(5, SECTIONS[4]),
        "  <h3>5.1 By folder set</h3>\n",
        f"  <p>Members are read as they are at report time, {escape(report_data.format_time(model['members_as_of']))}, "
        "not as at the end of the period. Attachment A lists every member with who decided their access, and "
        "Attachment B every group.</p>\n",
        f"  <p>{escape(CHANGES_COUNTED)}</p>\n",
        f"  {data_table(by_control_columns, rows, numeric=numeric)}\n",
        "  <h3>5.2 Access approvals</h3>\n",
        "  <p>Each approval of the access to one folder set is recorded in Polar Sky with the date and who approved it. "
        "An approval by a person is that person's review and sign-off; an approval whose approver type is Polar Sky was "
        "made by Polar Sky itself, not by a person. Approvers do not sign again at period end. The table below shows how "
        "many folder sets each approver approved in the period, and when; Attachment E lists every approval, including "
        "any from before the period that was still in force when it began.</p>\n",
        f"  {data_table(approver_columns, approver_rows, numeric=('controls',), css_class='owners')}\n" if approver_rows
        else "  <p>No access was approved during the period.</p>\n",
        "  <h3>5.3 Groups</h3>\n",
        f"  {data_table(group_columns, model['tables']['groups'], numeric=('people_count',))}\n" if model["tables"]["groups"]
        else "  <p>No groups.</p>\n",
        "  <h3>5.4 Kept direct shares</h3>\n",
        "  <p>Direct shares are read as they are now, not as at approval. Polar Sky does not record who decided to keep "
        "them or when.</p>\n",
        f"  {data_table(share_columns, model['tables']['shares'])}\n" if model["tables"]["shares"]
        else "  <p>No kept direct shares.</p>\n",
        "  <h3>5.5 Site owners and applications</h3>\n",
        f"  <p>{not_available()}.</p>\n",
        "</section>\n",
    ]
    return "".join(parts)


def approver_label(name, kind, owners):
    """Name an approver in the approvals table; Polar Sky's own approvals name the data owners of those folder sets."""
    if kind != report_data.APPROVER_SYSTEM:
        return name
    if not owners:
        return "Polar Sky; no data owner recorded"
    return f"Polar Sky; data {'owner' if len(owners) == 1 else 'owners'} {', '.join(sorted(owners))}"


def render_removals(model):
    totals = model["totals"]
    inputs = model["inputs"]
    columns = selected_columns(model, "removals")
    deadline = ("Removal deadline", value_or_tbd(inputs.get("removal_deadline")))
    within = deadline_check(model)
    if not totals["removals"]:
        return (
            section_heading(6, SECTIONS[5])
            + "  <h3>6.1 Removals</h3>\n  <p>No removals in the period.</p>\n"
            + "  <h3>6.2 Verification</h3>\n"
            + f"  {key_values([('Removals to verify', 'No removals'), deadline])}\n</section>\n"
        )
    rows = [
        ("Applied", escape(f"{number(totals['removals_applied'])} of {number(totals['removals'])}")),
        ("Failed", escape(number(totals["removals_failed"]))),
        ("Pending", escape(number(totals["removals_pending"]))),
        ("Not applied", escape(number(totals["removals_other"]))),
        ("Confirmed by re-scan", escape(rescan_confirmation(totals)) if totals["removals_recorded"] else not_available()),
        deadline,
        ("Within the deadline", escape(within) if within else not_available()),
    ]
    text = (
        f"Polar Sky made each removal in {model['provider_label']} after the access was approved, and recorded "
        "whether it was applied or failed. Attachment D lists every removal with its result and date."
    )
    if totals["removals_recorded"]:
        text += (
            " For each removal Polar Sky recorded, the decision is the latest approval of its folder set at or before "
            "the removal. The deadline check counts calendar days in UTC from the decision to the removal, or, for a "
            "removal not done by the end of the review period, to that day. The evidence covers the review period only, so a "
            "removal done after it is not shown here. A removal that failed or was pending, and "
            "that a later removal of the same access on the same folder set completed, says when it was done later; "
            "the deadline counts list that access once, by the later removal."
        )
    return (
        section_heading(6, SECTIONS[5])
        + f"  <p>{escape(text)}</p>\n"
        + "  <h3>6.1 Removals</h3>\n"
        + f"  {data_table(columns, model['tables']['removals'])}\n"
        + "  <h3>6.2 Verification</h3>\n"
        + f"  {key_values(rows)}\n</section>\n"
    )


def render_exceptions():
    return (
        section_heading(7, SECTIONS[6], first_on_page=False)
        + f"  <p>{not_available()}. Polar Sky does not record exceptions or time-limited access yet.</p>\n</section>\n"
    )


def render_signoff(model):
    acknowledgment = model["acknowledgment"]
    session = model["inputs"].get("session") or {}
    statement = acknowledgment.get("statement") or report_data.DEFAULT_ACKNOWLEDGMENT
    name = ", ".join(part for part in (acknowledgment.get("name"), acknowledgment.get("title")) if part)
    session_text = "Not recorded"
    if session.get("id"):
        session_text = session["id"]
    details = (
        f"<dt>Name</dt><dd>{value_or_tbd(name)}</dd>"
        f"<dt>Recorded</dt><dd>{value_or_tbd(report_data.format_date(acknowledgment.get('date')))}"
        f"{', typed into the Polar Sky compliance report skill in Claude Code' if acknowledgment.get('date') else ''}</dd>"
        f"<dt>Claude Code session</dt><dd><code>{escape(session_text)}</code></dd>"
    )
    return (
        section_heading(8, SECTIONS[7])
        + "  <p><b>Approvers.</b> Each approval of a folder set's access is the approver's sign-off, recorded in "
        "Polar Sky with the date (Section 5.2). Approvers do not sign this report.</p>\n"
        + '  <div class="attest"><span class="label">Management acknowledgment</span>\n'
        + f"    <p>{escape(statement)}</p>\n"
        + f"    <dl>{details}</dl>\n  </div>\n</section>\n"
    )


def render_attachments(model, hashes):
    definitions = report_data.load_reference("columns.json")
    letters = "ABCDE"
    body = ""
    for letter, table in zip(letters, TABLE_ORDER):
        definition = definitions[table]
        count = len(model["tables"][table])
        body += (
            f'<tbody class="att"><tr class="has-hash"><td>{letter}</td><td>{escape(definition["title"])}</td>'
            f"<td>{escape(definition['description'])} {number(count)} rows.</td><td><code>{escape(definition['file'])}</code></td></tr>"
            f'<tr><td></td><td class="hk">SHA-256</td><td colspan="2"><code>{hashes[definition["file"]]}</code></td></tr></tbody>'
        )
    body += extract_attachment(model["extract"], definitions[EXTRACT_TABLE], hashes)
    return (
        section_heading(9, SECTIONS[8])
        + "  <p>The attachments hold the detail behind every count in this report. Each row is complete on its own, "
        "so no row needs another file to be understood. Each attachment is delivered with this report, and its "
        "SHA-256 hash below ties it to this version.</p>\n"
        + f'  <table class="ps-table "><thead><tr><th></th><th>Attachment</th><th>Contents</th><th>File</th></tr></thead>{body}</table>\n'
        + "</section>\n"
    )


def extract_attachment(extract, definition, hashes):
    """Attachment F: the stored extract file and its rows as a CSV file, each with its own SHA-256."""
    if not extract:
        return f'<tbody class="att"><tr><td>F</td><td>Original extract</td><td colspan="2">{not_available()}</td></tr></tbody>'
    if not completed(extract):
        reason = extract["failure_reason"] or "Polar Sky gave no reason"
        return (
            '<tbody class="att"><tr><td>F</td><td>Original extract</td>'
            f'<td colspan="2">{escape(f"Not available. The extract failed: {reason}")}</td></tr></tbody>'
        )
    file = extract["file"]
    return (
        '<tbody class="att"><tr class="has-hash"><td>F</td><td>Original extract</td>'
        "<td>The stored extract that Section 3 counts from, kept write-once in Polar Sky. "
        f"{counted(extract['rows'], 'row', 'rows')}.</td>"
        f"<td class=\"p\"><code>{escape(file.get('reference') or '')}</code></td></tr>"
        f'<tr><td></td><td class="hk">SHA-256</td><td colspan="2"><code>{escape(file.get("sha256") or "")}</code></td></tr>'
        f"<tr class=\"has-hash\"><td></td><td>{escape(definition['title'])}</td>"
        f"<td>{escape(definition['description'])} {number(extract['rows_read'])} rows.</td>"
        f"<td><code>{escape(definition['file'])}</code></td></tr>"
        f'<tr><td></td><td class="hk">SHA-256</td><td colspan="2"><code>{hashes[definition["file"]]}</code></td></tr></tbody>'
    )


CSS_STRING_SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,:;_-/()#&+'!?%")


def css_string(value):
    """Escape text for a double-quoted CSS string inside a style element, so it cannot end the string or the element."""
    return "".join(character if character in CSS_STRING_SAFE else f"\\{ord(character):06X}" for character in str(value))


def render_html(model, hashes):
    """Lay out the whole report as one HTML document."""
    framework = model["framework"]
    inputs = model["inputs"]
    with open(os.path.join(ASSETS_DIRECTORY, "report.css"), encoding="utf-8") as handle:
        css = handle.read()
    css = (
        css.replace("{{running_title}}", css_string(framework["title"].replace('"', "'")))
        .replace("{{report_id}}", css_string(inputs["report_id"].replace('"', "'")))
        .replace("{{running_footer}}", css_string((inputs.get("running_footer") or "Confidential.").replace('"', "'")))
    )
    sections = [
        render_cover(model), render_contents(model), render_summary(model), render_scope(model),
        render_population(model), render_policy(model), render_results(model), render_removals(model),
        render_exceptions(), render_signoff(model), render_attachments(model, hashes),
    ]
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(framework['title'])}, {escape(inputs['organization'])}, {escape(inputs['report_id'])}</title>\n"
        f"<style>\n{css}</style>\n</head>\n<body>\n<div class=\"sheet\">\n\n"
        + "\n".join(sections)
        + "\n</div>\n</body>\n</html>\n"
    )


def clock_time():
    """Return the current UTC time to the second, as the render stamps it into the report."""
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


TBD_FIELDS = (
    ("requested_by", "Requested by"),
    ("procedure", "Review procedure"),
    ("removal_deadline", "Removal deadline"),
    ("retention", "Retention"),
)


def tbd_fields(model):
    """Name the report fields that show TBD because the person did not give them."""
    inputs = model["inputs"]
    fields = [label for key, label in TBD_FIELDS if inputs.get(key) in (None, "")]
    if model["framework_key"] in ("soc2", "sox") and not inputs.get("review_interval"):
        fields.append("Review interval")
    acknowledgment = model["acknowledgment"]
    if not acknowledgment.get("name"):
        fields.append("Management acknowledgment")
    elif not acknowledgment.get("date"):
        fields.append("Management acknowledgment date")
    if completed(model["extract"]) and not model["extract"]["file"].get("sha256"):
        fields.append("SHA-256 of extract")
    return fields


def not_available_parts(model):
    """Name the parts of the report marked not available in this version."""
    extract = model["extract"]
    totals = model["totals"]
    parts = []
    if not extract:
        parts += ["Section 3 extract taken, independent count and SHA-256 of extract", "Attachment F original extract"]
    if not completed(extract):
        parts += ["Section 3 how the list was built", "Section 3 link types not listed"]
    if totals["members"] and not totals["account_types_known"]:
        parts.append("Account types of members")
    parts += ["Section 4 separate access rules", "Section 5.5 site owners and applications"]
    if totals["removals"] and not totals["removals_recorded"]:
        parts.append("Section 6.2 confirmed by re-scan")
    if totals["removals"] and deadline_check(model) is None:
        parts.append("Section 6.2 within the deadline")
    parts.append("Section 7 exceptions")
    return parts


def extract_summary(extract):
    """Say in one line what became of the extract, as Section 3 states it."""
    if not extract:
        return NOT_AVAILABLE + "."
    if not completed(extract):
        reason = (extract["failure_reason"] or "Polar Sky gave no reason").rstrip(".")
        return f"Failed: {reason}. The report has no extract rows; Attachment F says the extract failed and has no file."
    sha256 = extract["file"].get("sha256") or "TBD"
    checked = {True: "checked", False: "not confirmed"}.get(extract["sha256_verified"], "not recorded as checked")
    exclusions = extract["exclusions"]
    could_not = counted(len(exclusions), "item", "items") if exclusions else "none"
    text = f"Taken {report_data.format_time(extract['as_of'])}. SHA-256 {sha256}, {checked} when its rows were read."
    if read_no_folder(extract):
        text += (
            " Polar Sky read no folder, so the extract is empty." if extract["exclusions"]
            else " No folder was in scope, so the extract is empty."
        )
    if not extract["row_hashes_match"]:
        text += " The row pages name a different SHA-256 than the stored file."
    if not extract["rows_read_match"]:
        text += (
            f" Rows read: {number(extract['rows_read'])}: {_kinds(extract['rows_read_by_kind'])}. This differs from "
            f"the extract's own row counts: {number(extract['rows'])}: {_kinds(extract['rows_by_kind'])}."
        )
    return f"{text} {independent_count(extract)} Could not be read: {could_not}."


def issued_text(model):
    """Say the issue date the report shows, and when it is the generation date because none was given."""
    issued = report_data.format_date(model["issued_at"])
    if model["inputs"].get("issued_at"):
        return issued
    return f"{issued}, the day the report was generated, as no issue date was given"


def summary_lines(model):
    """The figures the skill reports back to the person, worded as the report states them."""
    totals = model["totals"]
    people = number(totals["people_deciding"]) if totals["people_deciding"] else "no one"
    folder_sets = no_access_to_review(model) if no_folder_sets(model) else controls_population(totals) + "."
    lines = [
        f"Folder sets: {folder_sets}",
        f"Access decisions: {decisions_text(totals)}.",
        f"Members at report time: {members_text(model)}.",
        f"Removals: {checklist_evidence(model, 'removals')}",
        f"Kept direct shares: {shares_text(model)}.",
        f"People who approved access or added or changed it: {people}.",
        *([f"Approval by a person: {approved_by_polar_sky_only(totals)}"] if totals["controls_without_person"] else []),
        f"Extract: {extract_summary(model['extract'])}",
        *([f"Access not in the members list: {unlisted_text(model['unlisted'])}."] if model["unlisted"] is not None else []),
        f"Generated: {report_data.format_time(model['inputs']['generated_at'])}.",
        f"Issued: {issued_text(model)}.",
        "Not available in this version: " + "; ".join(not_available_parts(model)) + ".",
        "TBD: " + ("; ".join(tbd_fields(model)) if tbd_fields(model) else "nothing") + ".",
    ]
    return lines


def render_summary_text(model):
    """The summary block the render command prints after the file paths."""
    return "Summary, worded as the report states it:\n" + "".join(
        f"- {' '.join(line.split())}\n" for line in summary_lines(model)
    )


def render(data, generated_at=None):
    """Render the report data into a mapping of output file name to file text, stamping generated_at when given."""
    return render_with_model(data, generated_at)[0]


def render_with_model(data, generated_at=None):
    """Render the report data and return the output files with the model they were built from."""
    if generated_at is not None:
        data = {**data, "inputs": {**(data.get("inputs") or {}), "generated_at": generated_at}}
    model = report_data.build_model(data)
    definitions = report_data.load_reference("columns.json")
    files = {}
    for table in TABLE_ORDER:
        files[definitions[table]["file"]] = render_csv(selected_columns(model, table), model["tables"][table])
    if completed(model["extract"]):
        files[definitions[EXTRACT_TABLE]["file"]] = render_csv(
            selected_columns(model, EXTRACT_TABLE), model["extract"]["table"]
        )
    hashes = {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in files.items()}
    files["report.html"] = render_html(model, hashes)
    return files, model


def write_outputs(files, out_directory):
    """Write the rendered files and the fonts the HTML links to into the output folder, removing files an earlier render wrote that this one does not, and any earlier PDF."""
    os.makedirs(out_directory, exist_ok=True)
    generated = {definition["file"] for definition in report_data.load_reference("columns.json").values()}
    generated.add(PDF_FILE)
    for name in sorted(generated - set(files)):
        path = os.path.join(out_directory, name)
        if os.path.exists(path):
            os.remove(path)
    for name, text in files.items():
        with open(os.path.join(out_directory, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    fonts_target = os.path.join(out_directory, "fonts")
    shutil.copytree(os.path.join(ASSETS_DIRECTORY, "fonts"), fonts_target, dirs_exist_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True, help="report-data.json, or a folder with inputs.json and responses/")
    parser.add_argument("--out", help="Output folder")
    parser.add_argument("--check", action="store_true", help="Only print what to check with the person before rendering")
    arguments = parser.parse_args(argv)
    if not arguments.check and not arguments.out:
        parser.error("--out is required unless --check is given")
    try:
        files, model = render_with_model(report_data.load_data(arguments.data), generated_at=clock_time())
    except report_data.ReportDataError as error:
        print(f"Cannot render the report: {error}", file=sys.stderr)
        return 2
    if arguments.check:
        points = checks_before_rendering(model)
        print("Check before you render:" if points else "Nothing to check before you render.")
        for point in points:
            print(f"- {point}")
        return 0
    write_outputs(files, arguments.out)
    for name in sorted(files):
        print(os.path.join(arguments.out, name))
    print()
    print(render_summary_text(model), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
