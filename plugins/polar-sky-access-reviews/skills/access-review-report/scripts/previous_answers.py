"""Find the answers this skill wrote for earlier reports in the person's Claude Code sessions on this computer.

Usage: python3 previous_answers.py [--organization NAME]

Prints one JSON object: the most recent answers for each framework, and the most recent answers of any framework.
A report mapped to several frameworks counts for each of them.
Only answers the renderer accepts are printed; nothing else from the session files is.
"""

import argparse
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import report_data  # noqa: E402

MAXIMUM_FILES = 200
MAXIMUM_FILE_BYTES = 64 * 1024 * 1024
MAXIMUM_TOTAL_BYTES = 512 * 1024 * 1024
MAXIMUM_LINE_BYTES = 1024 * 1024
MAXIMUM_TEXT_LENGTH = 2000
INPUTS_PATH = re.compile(r"(?:^|[/\\])access-review-[A-Za-z0-9._-]+[/\\]inputs\.json$")
TEXT_ANSWERS = (
    "organization", "requested_by", "procedure", "removal_deadline", "retention", "review_interval", "control_owner",
    "data_source", "exclusions", "prepared_for", "running_footer",
)
ACKNOWLEDGMENT_ANSWERS = ("name", "title", "statement")
COLUMN_ID = re.compile(r"^[a-z0-9_]{1,64}$")


def sessions_folder():
    """The folder that holds the Claude Code session files, from CLAUDE_CONFIG_DIR or the home folder."""
    configuration = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(configuration, "projects")


def session_files(folder):
    """The newest session files directly inside each project folder, skipping links, subagent folders and large files."""
    found = []
    try:
        projects = list(os.scandir(folder))
    except OSError:
        return []
    for project in projects:
        if not project.is_dir(follow_symlinks=False):
            continue
        try:
            entries = list(os.scandir(project.path))
        except OSError:
            continue
        for entry in entries:
            if not entry.name.endswith(".jsonl") or not entry.is_file(follow_symlinks=False):
                continue
            try:
                status = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if status.st_size <= MAXIMUM_FILE_BYTES:
                found.append((status.st_mtime, entry.path))
    found.sort(reverse=True)
    return found[:MAXIMUM_FILES]


def _lines(handle, size):
    """Yield the lines in the first size bytes of a session file, up to MAXIMUM_LINE_BYTES each, skipping longer ones without holding them whole."""
    while handle.tell() < size:
        line = handle.readline(min(MAXIMUM_LINE_BYTES + 1, size - handle.tell()))
        if not line:
            return
        if len(line) <= MAXIMUM_LINE_BYTES:
            yield line.decode("utf-8", errors="replace")
            continue
        while line and not line.endswith(b"\n") and handle.tell() < size:
            line = handle.readline(min(MAXIMUM_LINE_BYTES, size - handle.tell()))


def _text(value):
    if isinstance(value, str) and value.strip() and len(value) <= MAXIMUM_TEXT_LENGTH:
        return value
    return None


def _table_ids(columns, table, defaults_only=False):
    """The column ids of a table in columns.json order, or only its default ones."""
    definitions = (columns.get(table) or {}).get("columns", []) if isinstance(table, str) else []
    return [column["id"] for column in definitions if column.get("default") or not defaults_only]


def _known_columns(chosen, columns):
    """Split the saved columns into the ids columns.json still has, per table in the saved order, and the ids it no longer has."""
    kept, unknown = {}, {}
    if not isinstance(chosen, dict):
        return kept, unknown
    for table, ids in chosen.items():
        known = set(_table_ids(columns, table))
        if not known or not isinstance(ids, list):
            continue
        names = [item for item in ids if isinstance(item, str)]
        kept_ids = list(dict.fromkeys(item for item in names if item in known))
        dropped = [item for item in dict.fromkeys(names) if item not in known and COLUMN_ID.match(item)]
        if kept_ids:
            kept[table] = kept_ids
        if dropped:
            unknown[table] = dropped
    return kept, unknown


def columns_last_time(inputs, columns):
    """Describe the columns of an earlier report: defaults when it saved none, the tables that differ from today's defaults, the saved ids columns.json no longer has, and today's default ids the saved tables leave out."""
    kept, unknown = _known_columns(inputs.get("columns"), columns)
    if not kept:
        return {"last_time": "defaults", "changed_tables": [], "no_longer_offered": unknown,
                "defaults_not_in_last": {}}
    changed = [table for table in columns if table in kept and kept[table] != _table_ids(columns, table, True)]
    missing = {}
    for table, ids in kept.items():
        left_out = [item for item in _table_ids(columns, table, True) if item not in ids]
        if left_out:
            missing[table] = left_out
    return {"last_time": "chosen", "changed_tables": changed, "no_longer_offered": unknown,
            "defaults_not_in_last": missing}


def framework_keys(inputs, frameworks):
    """The frameworks of an earlier report, from its one framework or its list of frameworks, or None when they are not ones the renderer accepts."""
    single, several = inputs.get("framework"), inputs.get("frameworks")
    if several is None:
        return [single] if isinstance(single, str) and single in frameworks else None
    if single is not None or not isinstance(several, list) or not several:
        return None
    if not all(isinstance(key, str) and key in frameworks for key in several) or len(set(several)) != len(several):
        return None
    return list(several)


def answer_frameworks(answers):
    """The frameworks a cleaned answer set counts for."""
    return answers.get("frameworks") or [answers["framework"]]


def clean_answers(inputs, frameworks, columns):
    """Keep only the answers the renderer accepts that hold from one report to the next, each of the type it expects."""
    keys = framework_keys(inputs, frameworks) if isinstance(inputs, dict) else None
    if keys is None:
        return None
    answers = {"frameworks": keys} if "frameworks" in inputs else {"framework": keys[0]}
    for key in TEXT_ANSWERS:
        if _text(inputs.get(key)):
            answers[key] = inputs[key]
    for key, example in (("removal_deadline_days", 30), ("review_interval_months", 6), ("review_interval_days", 90)):
        try:
            number = report_data.whole_number(inputs.get(key), key, example)
        except report_data.ReportDataError:
            number = None
        if number is not None:
            answers[key] = number
    acknowledgment = inputs.get("acknowledgment")
    if isinstance(acknowledgment, dict):
        kept = {key: acknowledgment[key] for key in ACKNOWLEDGMENT_ANSWERS if _text(acknowledgment.get(key))}
        if kept:
            answers["acknowledgment"] = kept
    kept_columns = _known_columns(inputs.get("columns"), columns)[0]
    if kept_columns:
        answers["columns"] = kept_columns
    logo = _text(inputs.get("logo"))
    if logo and os.path.isfile(os.path.expanduser(logo)):
        answers["logo"] = logo
    return answers


def _written_inputs(line):
    """Yield the record time and content of each Write of an access review inputs.json in one session file line."""
    try:
        record = json.loads(line)
    except ValueError:
        return
    if not isinstance(record, dict) or record.get("type") != "assistant":
        return
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("name") != "Write":
            continue
        tool_input = block.get("input")
        if not isinstance(tool_input, dict):
            continue
        path, text = tool_input.get("file_path"), tool_input.get("content")
        if isinstance(path, str) and isinstance(text, str) and INPUTS_PATH.search(path):
            yield record.get("timestamp"), text


def _record_time(value, fallback):
    try:
        return report_data.parse_time(value) if isinstance(value, str) and value else fallback
    except ValueError:
        return fallback


REPORT_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _matches(pattern, value):
    return isinstance(value, str) and pattern.match(value) is not None


def _last_report(inputs):
    """The earlier report's ID and period, each only when it has the expected form."""
    period = inputs.get("period") if isinstance(inputs.get("period"), dict) else {}
    report = {"report_id": (REPORT_ID, inputs.get("report_id")), "period_from": (DAY, period.get("from")),
              "period_to": (DAY, period.get("to"))}
    return {key: value for key, (pattern, value) in report.items() if _matches(pattern, value)}


def _open_session_file(path):
    """Open a session file without following a link, at the file or its project folder, only when it is still a regular file within the size limit; return the handle and its size, or None."""
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        folder = os.open(os.path.dirname(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | no_follow)
    except OSError:
        return None
    try:
        descriptor = os.open(
            os.path.basename(path), os.O_RDONLY | no_follow | getattr(os, "O_NONBLOCK", 0), dir_fd=folder
        )
    except OSError:
        return None
    finally:
        os.close(folder)
    status = os.fstat(descriptor)
    if not stat.S_ISREG(status.st_mode) or status.st_size > MAXIMUM_FILE_BYTES:
        os.close(descriptor)
        return None
    return os.fdopen(descriptor, "rb"), status.st_size


def find_previous_answers(folder=None, organization=None):
    """Return the most recent answers per framework and of any framework from the session files, only for the organization when one is given, or empty ones."""
    frameworks = report_data.load_reference("frameworks.json")
    columns = report_data.load_reference("columns.json")
    newest = {}
    budget = MAXIMUM_TOTAL_BYTES
    for modified, path in session_files(folder or sessions_folder()):
        file_time = datetime.fromtimestamp(modified, timezone.utc)
        opened = _open_session_file(path)
        if opened is None:
            continue
        handle, size = opened
        with handle:
            if size > budget:
                break
            budget -= size
            try:
                for line in _lines(handle, size):
                    if "inputs.json" not in line:
                        continue
                    for timestamp, text in _written_inputs(line):
                        try:
                            inputs = json.loads(text)
                        except ValueError:
                            continue
                        answers = clean_answers(inputs, frameworks, columns)
                        if answers and organization and (answers.get("organization") or "").casefold() != organization.casefold():
                            answers = None
                        if not answers:
                            continue
                        when = _record_time(timestamp, file_time)
                        for framework in answer_frameworks(answers):
                            known = newest.get(framework)
                            if known is None or when > known[0]:
                                newest[framework] = (
                                    when, answers, _last_report(inputs), columns_last_time(inputs, columns)
                                )
            except OSError:
                continue
    by_framework = {
        framework: {"date": when.strftime("%Y-%m-%d"), "answers": answers, "last_report": last_report,
                    "columns": columns_note}
        for framework, (when, answers, last_report, columns_note) in newest.items()
    }
    latest = max(newest, key=lambda framework: newest[framework][0], default=None)
    return {"by_framework": by_framework, "latest": by_framework[latest] if latest else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--organization", help="Only answers from earlier reports for this organization")
    arguments = parser.parse_args(argv)
    try:
        result = find_previous_answers(organization=arguments.organization)
    except Exception:  # noqa: BLE001
        result = {"by_framework": {}, "latest": None}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
