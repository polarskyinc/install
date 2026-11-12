"""Golden and behaviour tests for the access review audit trail renderer.

Run from the install repository root: python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-audit-trail/tests
Set UPDATE_GOLDEN=1 to rewrite the golden files after an intended change.
"""

import copy
import csv
import io
import json
import os
import sys
import tempfile
import unittest

TESTS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
SKILL_DIRECTORY = os.path.dirname(TESTS_DIRECTORY)
sys.path.insert(0, os.path.join(SKILL_DIRECTORY, "scripts"))

import render_audit_trail  # noqa: E402

FIXTURE = os.path.join(TESTS_DIRECTORY, "fixtures", "northwind.json")
GOLDEN_DIRECTORY = os.path.join(TESTS_DIRECTORY, "golden")
FIRST_DAY = "2026-09-01"
LAST_DAY = "2026-09-30"


def fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)["responses"]


def trail_pages(responses):
    return [entry for entry in responses if entry["tool"] == render_audit_trail.TOOL_AUDIT_TRAIL]


def render(responses, first_day=FIRST_DAY, last_day=LAST_DAY, control_id=None):
    return render_audit_trail.render(responses, first_day, last_day, control_id)


def rows_of(text):
    return list(csv.DictReader(io.StringIO(text, newline="")))


def single_page(first_day, last_day, entries, control_id=None):
    arguments = {"from": first_day, "to": last_day}
    if control_id:
        arguments["control_id"] = control_id
    return {
        "tool": render_audit_trail.TOOL_AUDIT_TRAIL,
        "arguments": arguments,
        "response": {"from": first_day, "to": last_day, "control_id": control_id, "entries": entries, "next_cursor": None},
    }


class GoldenTest(unittest.TestCase):
    def test_output_matches_golden_files(self):
        files = render(fixture())
        self.assertEqual(sorted(files), ["audit-trail.csv", "audit-trail.md"])
        for name, text in files.items():
            path = os.path.join(GOLDEN_DIRECTORY, name)
            if os.environ.get("UPDATE_GOLDEN"):
                with open(path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(text)
            with open(path, encoding="utf-8", newline="") as handle:
                self.assertEqual(text, handle.read(), f"{name} differs from its golden file")

    def test_rendering_twice_gives_the_same_bytes(self):
        self.assertEqual(render(fixture()), render(fixture()))

    def test_a_folder_of_saved_responses_renders_like_the_fixture_file(self):
        with tempfile.TemporaryDirectory() as directory:
            os.makedirs(os.path.join(directory, "responses"))
            for index, entry in enumerate(fixture(), start=1):
                path = os.path.join(directory, "responses", f"{index:03d}-{entry['tool']}.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(entry, handle)
            self.assertEqual(render(render_audit_trail.load_responses(directory)), render(fixture()))


class ContentTest(unittest.TestCase):
    def setUp(self):
        self.files = render(fixture())
        self.rows = rows_of(self.files["audit-trail.csv"])

    def test_one_row_per_change_oldest_first(self):
        self.assertEqual(len(self.rows), 7)
        self.assertEqual([row["when"] for row in self.rows], sorted(row["when"] for row in self.rows))
        self.assertEqual(self.rows[0]["what_changed"], "Control approved")

    def test_a_removal_names_its_approval_result_confirmation_and_change_reference(self):
        removal = next(row for row in self.rows if row["change_reference"])
        self.assertEqual(removal["made_by"], "Polar Sky")
        self.assertEqual(removal["approved_by"], "Priya Natarajan")
        self.assertEqual(removal["approved_at"], "2026-09-02 09:00:00 UTC")
        self.assertEqual(removal["result"], "Removed")
        self.assertEqual(removal["confirmed_at"], "2026-09-03 11:00:01 UTC")
        self.assertEqual(removal["change_reference"], "permission-9")

    def test_a_change_with_no_approval_recorded_says_so_and_an_event_leaves_it_empty(self):
        sources = {row["source"]: row for row in self.rows if row["approved_by"] == "Not recorded"}
        self.assertEqual(sorted(sources), ["plan", "removal_record"])
        self.assertTrue(all(row["approved_by"] == "" for row in self.rows if row["source"] == "event"))

    def test_plan_actions_show_before_and_after_where_recorded(self):
        plans = [row for row in self.rows if row["source"] == "plan"]
        self.assertEqual(plans[0]["before"], '[{"principal":"Payroll-Contractors","role":"write"}]')
        self.assertEqual(plans[0]["after"], "[]")
        self.assertEqual((plans[1]["before"], plans[1]["after"]), ("", ""))
        self.assertTrue(all(row["before"] == "" for row in self.rows if row["source"] != "plan"))

    def test_the_maker_of_an_event_names_where_they_made_it(self):
        self.assertEqual(self.rows[0]["made_through"], "AI assistant (Claude)")
        self.assertEqual(self.rows[1]["made_through"], "Polar Sky console")

    def test_csv_cells_that_start_a_formula_get_a_leading_quote(self):
        self.assertEqual(self.rows[2]["details"], "'=HYPERLINK(\"http://example.test\")")
        for text in ("=1", "+1", "-1", "@1", "\t1", "\r1"):
            self.assertEqual(render_audit_trail.csv_cell(text), "'" + text)
        self.assertEqual(render_audit_trail.csv_cell("Ana Diaz"), "Ana Diaz")

    def test_markdown_cells_stay_on_one_line_and_escape_formatting(self):
        self.assertEqual(render_audit_trail.markdown_cell("a | b\nc"), "a \\| b c")
        self.assertEqual(render_audit_trail.markdown_cell("[link](x) *bold* <b>"), "\\[link\\](x) \\*bold\\* \\<b\\>")
        table_lines = [line for line in self.files["audit-trail.md"].splitlines() if line.startswith("| 2026")]
        self.assertEqual(len(table_lines), 7)

    def test_the_heading_counts_the_results(self):
        self.assertIn("7 changes, oldest first. Removals and plan actions: Applied 1, Failed 1, Pending 1, Removed 1.",
                      self.files["audit-trail.md"])

    def test_one_control_is_named_in_the_heading(self):
        control_id = "22222222-2222-4222-8222-222222222222"
        entries = [entry for entry in trail_pages(fixture())[0]["response"]["entries"] if entry["control_id"] == control_id]
        files = render([single_page(FIRST_DAY, LAST_DAY, entries, control_id)], control_id=control_id)
        self.assertIn("(UTC), control Payroll-Editors\n", files["audit-trail.md"])
        self.assertNotIn("every control", files["audit-trail.md"])

    def test_roles_are_named_as_the_report_names_them(self):
        event = copy.deepcopy(trail_pages(fixture())[0]["response"]["entries"][0])
        event.update({"source": "event", "change": "Role changed", "person_name": "Bo Chen",
                      "from_role": "reader", "to_role": "writer"})
        row = rows_of(render([single_page(FIRST_DAY, LAST_DAY, [event])])["audit-trail.csv"])[0]
        self.assertEqual(row["details"], "Bo Chen, Viewer to Editor")

    def test_a_removal_names_the_access_it_took_and_a_lowering_its_roles(self):
        removal = next(entry for entry in trail_pages(fixture())[0]["response"]["entries"]
                       if entry["source"] == "removal_record")
        removed = dict(removal, role="read")
        lowered = dict(removal, role="write", from_role="write", to_role="read", action="Lower access",
                       change="Lower access", at="2026-09-03T11:05:00Z", change_reference="permission-10")
        rows = rows_of(render([single_page(FIRST_DAY, LAST_DAY, [removed, lowered])])["audit-trail.csv"])
        self.assertIn("Ana Diaz (ana.diaz@northwind-demo.com), Read access, on ", rows[0]["details"])
        self.assertEqual(rows[0]["result"], "Removed")
        self.assertIn("Ana Diaz (ana.diaz@northwind-demo.com), Edit to Read, on ", rows[1]["details"])
        self.assertEqual(rows[1]["result"], "Lowered")

    def test_a_removal_shows_the_step_the_tool_words(self):
        link = next(row for row in self.rows if row["what_changed"] == "Remove a sharing link")
        self.assertEqual(link["details"],
                         "Removes the anonymous sharing link on Catalog / Product Adoption / EMEA / launch deck.pptx.")

    def test_a_removal_without_a_step_starts_with_a_capital_and_names_the_link_scope_once(self):
        removal = next(entry for entry in trail_pages(fixture())[0]["response"]["entries"]
                       if entry["source"] == "removal_record")
        link = {key: value for key, value in removal.items() if key not in ("email", "step")}
        link.update(principal="anyone in the organization with the link", grantee_kind="link",
                    link_scope="organization", role="read", target="/Customer Records")
        row = rows_of(render([single_page(FIRST_DAY, LAST_DAY, [link])])["audit-trail.csv"])[0]
        self.assertEqual(row["details"], "Anyone in the organization with the link, Read access, on /Customer Records")

    def test_a_removal_without_a_step_keeps_a_link_scope_its_principal_does_not_name(self):
        removal = next(entry for entry in trail_pages(fixture())[0]["response"]["entries"]
                       if entry["source"] == "removal_record")
        link = {key: value for key, value in removal.items() if key not in ("email", "step")}
        link.update(principal="a sharing link", grantee_kind="link",
                    link_scope="anonymous", role="read", target="/Customer Records")
        row = rows_of(render([single_page(FIRST_DAY, LAST_DAY, [link])])["audit-trail.csv"])[0]
        self.assertEqual(row["details"], "A sharing link, Read access, on /Customer Records, link scope anonymous")

    def test_an_empty_range_says_no_changes_were_recorded(self):
        files = render([single_page(FIRST_DAY, LAST_DAY, [])])
        self.assertIn("Polar Sky recorded no changes in this range.", files["audit-trail.md"])
        self.assertEqual(rows_of(files["audit-trail.csv"]), [])

    def test_a_range_split_in_two_lists_a_change_in_both_parts_once(self):
        entry = trail_pages(fixture())[0]["response"]["entries"][0]
        files = render(
            [single_page("2026-01-01", "2026-09-02", [entry]), single_page("2026-09-02", "2027-01-31", [entry])],
            first_day="2026-01-01", last_day="2027-01-31",
        )
        self.assertEqual(len(rows_of(files["audit-trail.csv"])), 1)


class RefusalTest(unittest.TestCase):
    def assert_refused(self, responses, message, **arguments):
        with self.assertRaises(render_audit_trail.AuditTrailDataError) as raised:
            render(responses, **arguments)
        self.assertIn(message, str(raised.exception))

    def test_a_missing_page_is_refused(self):
        responses = [entry for entry in fixture() if (entry["arguments"].get("cursor") is None)]
        self.assert_refused(responses, "is missing its page at cursor eyJwYWdlIjoyfQ")

    def test_a_missing_first_page_is_refused(self):
        responses = [entry for entry in fixture() if entry["arguments"].get("cursor")]
        self.assert_refused(responses, "is missing its first page")

    def test_a_refused_page_that_was_not_fetched_again_is_refused(self):
        responses = fixture()[:3]
        self.assert_refused(responses, "was refused (rate_limited)")

    def test_administrator_required_is_explained_plainly(self):
        refused = {
            "tool": render_audit_trail.TOOL_AUDIT_TRAIL,
            "arguments": {"from": FIRST_DAY, "to": LAST_DAY},
            "response": {"refused": True, "reason": "administrator_required", "message": "This tool is for administrators."},
        }
        self.assert_refused([refused], "only for Polar Sky administrators and named control reviewers")

    def test_a_gap_in_the_range_is_refused(self):
        self.assert_refused(
            [single_page("2026-01-01", "2026-06-30", []), single_page("2026-07-02", "2027-01-31", [])],
            "No get_access_review_audit_trail response covers 2026-07-01 to 2027-01-31",
            first_day="2026-01-01", last_day="2027-01-31",
        )

    def test_a_call_outside_the_range_is_refused(self):
        self.assert_refused([single_page("2026-08-31", LAST_DAY, [])], "reaches outside the requested range")

    def test_a_call_for_another_control_is_refused(self):
        self.assert_refused(
            [single_page(FIRST_DAY, LAST_DAY, [], "33333333-3333-4333-8333-333333333333")],
            "not every control",
        )

    def test_two_different_pages_for_one_cursor_are_refused(self):
        responses = fixture()
        changed = copy.deepcopy(trail_pages(responses)[0])
        changed["response"]["entries"] = []
        self.assert_refused(responses + [changed], "Two different pages")

    def test_no_audit_trail_response_is_refused(self):
        self.assert_refused(fixture()[:1], "holds no get_access_review_audit_trail response")


if __name__ == "__main__":
    unittest.main()
