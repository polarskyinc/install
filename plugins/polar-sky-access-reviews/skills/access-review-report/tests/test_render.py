"""Golden and behaviour tests for the access review report renderer.

Run from the install repository root: python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-report/tests
Set UPDATE_GOLDEN=1 to rewrite the golden files after an intended change.
"""

import base64
import copy
import csv
import html
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

TESTS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
SKILL_DIRECTORY = os.path.dirname(TESTS_DIRECTORY)
sys.path.insert(0, os.path.join(SKILL_DIRECTORY, "scripts"))

import render_report  # noqa: E402
import report_data  # noqa: E402

FIXTURE = os.path.join(TESTS_DIRECTORY, "fixtures", "northwind.json")
GOLDEN_DIRECTORY = os.path.join(TESTS_DIRECTORY, "golden")


def fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def rows_of(text):
    return list(csv.DictReader(io.StringIO(text, newline="")))


class GoldenTest(unittest.TestCase):
    def test_output_matches_golden_files(self):
        files = render_report.render(fixture())
        self.assertEqual(
            sorted(files),
            ["approvals.csv", "extract.csv", "groups.csv", "members.csv", "removals.csv", "report.html", "shares.csv"],
        )
        for name, text in files.items():
            path = os.path.join(GOLDEN_DIRECTORY, name)
            if os.environ.get("UPDATE_GOLDEN"):
                with open(path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(text)
            with open(path, encoding="utf-8", newline="") as handle:
                self.assertEqual(text, handle.read(), f"{name} differs from its golden file")

    def test_rendering_twice_gives_the_same_bytes(self):
        self.assertEqual(render_report.render(fixture()), render_report.render(fixture()))


class FrameworkTest(unittest.TestCase):
    def test_every_framework_renders_its_cover_page(self):
        frameworks = report_data.load_reference("frameworks.json")
        self.assertEqual(sorted(frameworks), ["hipaa", "pci_dss", "soc2", "sox"])
        for key, framework in frameworks.items():
            with self.subTest(framework=key):
                data = fixture()
                data["inputs"]["framework"] = key
                page = render_report.render(data)["report.html"]
                cover = page.split('<section class="cover">', 1)[1].split("</section>", 1)[0]
                self.assertIn(render_report.escape(framework["eyebrow"]), cover)
                self.assertIn(f"<h1>{render_report.escape(framework['title'])}</h1>", cover)
                self.assertIn("Northwind Traders&#x27;s Microsoft 365 tenant", cover)
                self.assertNotIn("{", cover.split("</svg>", 1)[1])
                self.assertIn(render_report.escape(framework["checklist_heading"]), page)
                self.assertIn(render_report.escape(framework["requirement"]), page)

    def test_unknown_framework_is_refused(self):
        data = fixture()
        data["inputs"]["framework"] = "iso27001"
        with self.assertRaises(report_data.ReportDataError):
            render_report.render(data)


PNG_LOGO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SVG_LOGO = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n<!-- logo -->\n'
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script>'
    b'<rect width="10" height="10"/></svg>\n'
)


def cover_of(page):
    return page.split('<section class="cover">', 1)[1].split("</section>", 1)[0]


class LogoTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def logo_file(self, name, content):
        path = os.path.join(self.directory.name, name)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def render_with_logo(self, path):
        data = fixture()
        data["inputs"]["logo"] = path
        return render_report.render(data)["report.html"]

    def assertRefused(self, path, *parts):
        with self.assertRaises(report_data.ReportDataError) as raised:
            self.render_with_logo(path)
        for part in parts:
            self.assertIn(part, str(raised.exception))

    def test_a_png_logo_is_embedded_on_the_cover(self):
        cover = cover_of(self.render_with_logo(self.logo_file("logo.png", PNG_LOGO)))
        source = "data:image/png;base64," + base64.b64encode(PNG_LOGO).decode("ascii")
        self.assertIn(f'<img class="customer-logo" src="{source}" alt="Northwind Traders logo">', cover)
        self.assertNotIn("Customer logo", cover)

    def test_a_jpeg_logo_is_embedded_on_the_cover(self):
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 32
        cover = cover_of(self.render_with_logo(self.logo_file("logo.JPG", content)))
        self.assertIn('src="data:image/jpeg;base64,' + base64.b64encode(content).decode("ascii") + '"', cover)

    def test_an_svg_logo_is_shown_through_an_img_element_and_its_script_never_reaches_the_html(self):
        page = self.render_with_logo(self.logo_file("logo.svg", SVG_LOGO))
        cover = cover_of(page)
        self.assertIn('<img class="customer-logo" src="data:image/svg+xml;base64,' + base64.b64encode(SVG_LOGO).decode("ascii"), cover)
        self.assertNotIn("<script", page)
        self.assertNotIn("alert(1)", page)

    def test_without_a_logo_the_cover_has_no_logo_box_or_placeholder(self):
        for value in (None, ""):
            with self.subTest(logo=value):
                data = fixture()
                data["inputs"]["logo"] = value
                cover = cover_of(render_report.render(data)["report.html"])
                self.assertNotIn("customer-logo", cover)
                self.assertNotIn("Customer logo", cover)
                self.assertNotIn("<img", cover)

    def test_a_logo_path_starting_with_the_home_folder_is_expanded(self):
        self.logo_file("logo.png", PNG_LOGO)
        with mock.patch.dict(os.environ, {"HOME": self.directory.name}):
            cover = cover_of(self.render_with_logo("~/logo.png"))
        self.assertIn('src="data:image/png;base64,', cover)

    def test_a_file_of_another_type_is_refused(self):
        path = self.logo_file("logo.gif", b"GIF89a" + b"\x00" * 32)
        self.assertRefused(path, "is not a PNG, JPEG or SVG file", "or no logo")

    def test_a_file_whose_content_is_not_the_type_its_name_says_is_refused(self):
        for name, content in (
            ("logo.png", b"GIF89a" + b"\x00" * 32),
            ("logo.png", b"\xff\xd8\xff\xe0" + b"\x00" * 32),
            ("logo.svg", b"<html><script>alert(1)</script></html>"),
            ("logo.svg", b"<!DOCTYPE html [<!ENTITY x 'y'>]><svg></svg>"),
            ("logo.jpg", b""),
        ):
            with self.subTest(name=name, content=content[:12]):
                self.assertRefused(self.logo_file(name, content), "is not a", "though its name ends in")

    def test_a_missing_logo_file_is_refused(self):
        self.assertRefused(os.path.join(self.directory.name, "missing.png"), "does not exist", "or no logo")

    def test_a_logo_file_that_cannot_be_read_is_refused(self):
        path = self.logo_file("logo.png", PNG_LOGO)
        with mock.patch("builtins.open", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(report_data.ReportDataError) as raised:
                report_data.load_logo(path)
        self.assertIn("cannot be read (Permission denied)", str(raised.exception))

    def test_a_folder_given_as_the_logo_is_refused(self):
        self.assertRefused(self.directory.name, "does not exist")

    def test_a_logo_larger_than_two_megabytes_is_refused(self):
        too_large = self.logo_file("logo.png", PNG_LOGO + b"\x00" * (report_data.LOGO_MAXIMUM_BYTES - len(PNG_LOGO) + 1))
        self.assertRefused(too_large, "larger than 2 MB")
        just_fits = self.logo_file("fits.png", PNG_LOGO + b"\x00" * (report_data.LOGO_MAXIMUM_BYTES - len(PNG_LOGO)))
        self.assertIn('class="customer-logo"', cover_of(self.render_with_logo(just_fits)))

    def test_a_logo_that_is_not_a_path_is_refused(self):
        self.assertRefused({"path": "logo.png"}, "must be the path to a logo file")

    def test_the_render_command_writes_no_logo_file_into_the_output_folder(self):
        data = fixture()
        data["inputs"]["logo"] = self.logo_file("logo.svg", SVG_LOGO)
        data_file = os.path.join(self.directory.name, "data.json")
        with open(data_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        out = os.path.join(self.directory.name, "report")
        with mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(render_report.main(["--data", data_file, "--out", out]), 0)
        self.assertEqual(
            sorted(os.listdir(out)),
            ["approvals.csv", "extract.csv", "fonts", "groups.csv", "members.csv", "removals.csv", "report.html", "shares.csv"],
        )

    def test_a_refused_logo_stops_the_render_command_with_the_reason(self):
        data = fixture()
        data["inputs"]["logo"] = os.path.join(self.directory.name, "missing.png")
        data_file = os.path.join(self.directory.name, "data.json")
        with open(data_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        error = io.StringIO()
        with mock.patch("sys.stderr", error):
            self.assertEqual(render_report.main(["--data", data_file, "--out", os.path.join(self.directory.name, "out")]), 2)
        self.assertIn("Cannot render the report: The logo file", error.getvalue())


class ContentTest(unittest.TestCase):
    def setUp(self):
        self.files = render_report.render(fixture())
        self.members = {row["person_name"]: row for row in rows_of(self.files["members.csv"])}

    def test_who_decided_comes_from_provenance(self):
        self.assertEqual(self.members["Leah Brooks"]["decided_by"], "Polar Sky")
        self.assertEqual(self.members["Leah Brooks"]["decided_on"], "2026-05-04")
        self.assertEqual(self.members["Sam Ortiz"]["decided_by"], "Dana Whitfield")
        self.assertEqual(self.members["Sam Ortiz"]["decided_on"], "2026-09-15")

    def test_reason_uses_basis_then_falls_back_to_the_control_reason(self):
        self.assertTrue(self.members["Sam Ortiz"]["reason"].startswith("Presents APAC product adoption"))
        self.assertEqual(
            self.members["Leah Brooks"]["reason"],
            "Proposed by Polar Sky: Members of the Catalog product and business development teams who report on product adoption.",
        )
        self.assertEqual(self.members["Omar Haddad"]["reason"], "Proposed by Polar Sky")
        self.assertEqual(self.members["Mia Novak"]["reason"], "Added or changed by Dana Whitfield")

    def test_members_from_every_page_are_listed(self):
        self.assertEqual(len(self.members), 7)

    def test_csv_is_rfc_4180(self):
        for name in ("members.csv", "groups.csv", "shares.csv", "removals.csv", "approvals.csv", "extract.csv"):
            text = self.files[name]
            self.assertTrue(text.endswith("\r\n"), name)
            self.assertNotIn("\n", text.replace("\r\n", ""), name)
            self.assertFalse(text.startswith("﻿"), name)
        self.assertIn('"Senior Director, Business Development, APAC"', self.files["members.csv"])

    def test_csv_cells_that_start_a_formula_are_escaped(self):
        member = self.members["'+Formula Plus"]
        self.assertEqual(member["email"], "'@formula.at@northwind-demo.com")
        self.assertEqual(member["title"], "'=HYPERLINK(\"http://example.com\")")
        self.assertEqual(member["reason"], "'-2+3 reviewer for model evaluations")
        shares = {row["email"]: row for row in rows_of(self.files["shares.csv"])}
        self.assertEqual(shares["tab.person@northwind-demo.com"]["person_name"], "'\tTab Person")
        self.assertEqual(shares["tab.person@northwind-demo.com"]["item"], "'\rCarriage return item.docx")
        self.assertEqual(self.members["Leah Brooks"]["title"], "Data Analyst")
        page = self.files["report.html"]
        self.assertIn("<td>\tTab Person</td>", page)
        self.assertIn("<td class=\"p\">\rCarriage return item<wbr>.docx</td>", page)
        self.assertNotIn("&#x27;\tTab Person", page)

    def test_email_and_path_cells_break_only_after_at_and_before_dot_hyphen_and_slash(self):
        page = self.files["report.html"]
        self.assertIn('<td class="p">sam<wbr>.ortiz@<wbr>northwind<wbr>-demo<wbr>.com</td>', page)
        self.assertIn('<td class="p">Catalog <wbr>/ Product Adoption <wbr>/ APAC <wbr>/ Q3 adoption<wbr>.xlsx</td>', page)
        self.assertIn('<td class="p">Catalog<wbr>-Client<wbr>-Viewers</td>', page)

    def test_break_points_stay_out_of_the_csv_files(self):
        for name, text in self.files.items():
            if name.endswith(".csv"):
                self.assertNotIn("<wbr>", text, name)
        shares = {row["email"]: row for row in rows_of(self.files["shares.csv"])}
        self.assertEqual(
            shares["sam.ortiz@northwind-demo.com"]["item"], "Catalog / Product Adoption / APAC / Q3 adoption.xlsx"
        )

    def test_break_points_escape_each_piece(self):
        self.assertEqual(render_report.breakable("a&b@x-y.com"), "a&amp;b@<wbr>x<wbr>-y<wbr>.com")
        self.assertEqual(render_report.breakable("/Shared"), "/Shared")
        self.assertEqual(render_report.breakable(None), "")

    def test_email_and_path_cells_can_still_break_inside_a_piece_that_does_not_fit(self):
        with open(os.path.join(render_report.ASSETS_DIRECTORY, "report.css"), encoding="utf-8") as handle:
            stylesheet = handle.read()
        self.assertIn(".ps-table td.p { overflow-wrap: anywhere;", stylesheet)

    def test_chosen_columns_set_the_header_in_the_chosen_order(self):
        header = self.files["removals.csv"].split("\r\n", 1)[0]
        self.assertEqual(
            header, "folder_set,action,step,target,principal,role,state,state_at,state_reason"
        )
        self.assertNotIn("<th>Folders</th><th>Action</th>", self.files["report.html"])

    def test_unknown_column_is_refused(self):
        data = fixture()
        data["inputs"]["columns"]["members"] = ["person_name", "salary"]
        with self.assertRaises(report_data.ReportDataError):
            render_report.render(data)

    def test_activity_outside_the_period_is_not_counted(self):
        model = report_data.build_model(fixture())
        by_name = {control["name"]: control for control in model["controls"]}
        self.assertEqual(by_name["Catalog-Client-Viewers"]["activity_in_period"], 3)

    def test_attachments_carry_the_hash_of_each_csv(self):
        import hashlib

        for name in ("members.csv", "removals.csv"):
            digest = hashlib.sha256(self.files[name].encode("utf-8")).hexdigest()
            self.assertIn(digest, self.files["report.html"])

    def test_missing_extract_is_marked_not_available(self):
        files = render_report.render(without_extract(fixture()))
        page = files["report.html"]
        self.assertNotIn("extract.csv", files)
        self.assertIn("<td>SHA-256 of extract</td><td><span class=\"na\">Not available in this version</span>", page)
        self.assertIn(
            "<td>F</td><td>Original extract</td><td colspan=\"2\"><span class=\"na\">Not available in this version</span>", page
        )
        self.assertIn("Re-scan confirmation: not available in this version.", page)
        self.assertIn("<td>How the list was built</td><td><span class=\"na\">Not available in this version</span>", page)
        self.assertIn("<td>Link types not listed</td><td><span class=\"na\">Not available in this version</span>", page)

    def test_members_are_labeled_as_at_report_time(self):
        files = render_report.render(without_extract(fixture()))
        self.assertEqual({row["as_of"] for row in rows_of(files["members.csv"])}, {"2026-11-02 14:02 UTC"})
        page = files["report.html"]
        self.assertIn("<th class=\"n\">Members at report time</th>", page)
        self.assertIn("Members are read as they are at report time, 2026-11-02 14:02 UTC, not as at the end of the period.", page)

    def test_members_take_the_extract_time_when_the_extract_completed(self):
        self.assertEqual({row["as_of"] for row in self.members.values()}, {"2026-11-02 13:55 UTC"})
        self.assertIn("Members are read as they are at report time, 2026-11-02 13:55 UTC", self.files["report.html"])

    def test_session_id_is_recorded_next_to_the_acknowledgment(self):
        page = self.files["report.html"]
        acknowledgment = page.split("Management acknowledgment</span>", 1)[1]
        self.assertIn("72fad66e-0000-4000-8000-000000000001", acknowledgment)

    def test_missing_session_says_not_recorded(self):
        data = fixture()
        del data["inputs"]["session"]
        page = render_report.render(data)["report.html"]
        self.assertIn("<dt>Claude Code session</dt><dd><code>Not recorded</code>", page)

    def test_customer_data_is_escaped(self):
        data = fixture()
        data["responses"][0]["response"]["controls"][0]["name"] = "<script>alert(1)</script>"
        page = render_report.render(data)["report.html"]
        self.assertNotIn("<script>", page)

    def test_a_control_listed_in_two_date_ranges_keeps_both_ranges(self):
        data = fixture()
        first = data["responses"][0]
        second = copy.deepcopy(first)
        second["arguments"] = {"from": "2025-11-01", "to": "2026-04-30"}
        data["inputs"]["period"] = {"from": "2025-11-01", "to": "2026-10-31"}
        control = second["response"]["controls"][0]
        control["approvals"] = [
            {"at": "2025-10-20T09:00:00Z", "carried_into_range": True, "actor": {"type": "user", "name": "Dana Whitfield"}},
            {"at": "2026-01-10T10:00:00Z", "carried_into_range": False, "actor": {"type": "user", "name": "Dana Whitfield"}},
        ]
        control["removals"] = [{"action": "Remove a grant", "step": "Remove Kai.", "target": "APAC", "state": "failed", "at": "2026-01-11T10:00:00Z"}]
        data["responses"].insert(1, second)
        model = report_data.build_model(data)
        control = next(item for item in model["controls"] if item["name"] == "Catalog-Client-Viewers")
        self.assertEqual(control["counts"]["removals"], 2)
        approvals = [row for row in model["tables"]["approvals"] if row["folder_set"] == "Catalog-Client-Viewers"]
        self.assertEqual(
            [(row["approved_at"], row["carried_into_period"]) for row in approvals],
            [("2025-10-20 09:00 UTC", "Yes"), ("2026-01-10 10:00 UTC", "No"), ("2026-09-15 16:20 UTC", "No")],
        )

    def test_a_later_empty_kept_shares_list_replaces_an_earlier_one(self):
        data = fixture()
        first = data["responses"][0]
        with_shares = next(control for control in first["response"]["controls"] if control.get("kept_direct_shares"))
        second = copy.deepcopy(first)
        second["arguments"] = {"from": "2025-11-01", "to": "2026-04-30"}
        data["inputs"]["period"] = {"from": "2025-11-01", "to": "2026-10-31"}
        for control in second["response"]["controls"]:
            if control["control_id"] == with_shares["control_id"]:
                control["kept_direct_shares"] = []
        data["responses"].insert(1, second)
        model = report_data.build_model(data)
        control = next(item for item in model["controls"] if item["id"] == with_shares["control_id"])
        self.assertEqual(control["counts"]["shares"], 0)

    def test_report_values_cannot_close_the_style_element(self):
        data = fixture()
        data["inputs"]["report_id"] = 'AR-1</style><script>alert(1)</script>'
        data["inputs"]["running_footer"] = "Footer\\\" } body { display: none"
        page = render_report.render(data)["report.html"]
        style = page.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertNotIn("<script>", page)
        self.assertNotIn("<", style)
        self.assertIn("AR-1\\00003C/style\\00003E", style)
        self.assertIn("Footer\\00005C' \\00007D body \\00007B display: none", style)

    def test_an_approval_listed_in_one_range_and_carried_into_the_next_counts_once(self):
        data = fixture()
        first = data["responses"][0]
        later = copy.deepcopy(first)
        later["arguments"] = {"from": "2026-11-01", "to": "2026-12-31"}
        for control in later["response"]["controls"]:
            control["approvals"] = [dict(approval, carried_into_range=True) for approval in control.get("approvals") or []][-1:]
            control["removals"] = []
        data["responses"].insert(0, later)
        data["inputs"]["period"] = {"from": "2026-05-01", "to": "2026-12-31"}
        expected = report_data.build_model(fixture())["tables"]["approvals"]
        approvals = report_data.build_model(data)["tables"]["approvals"]
        self.assertEqual(
            [(row["folder_set"], row["approved_at"], row["carried_into_period"]) for row in approvals],
            [(row["folder_set"], row["approved_at"], row["carried_into_period"]) for row in expected],
        )

    def test_sites_are_marked_incomplete_when_a_control_has_more_folders_than_listed(self):
        data = fixture()
        data["inputs"]["framework"] = "hipaa"
        complete = render_report.render(copy.deepcopy(data))["report.html"]
        self.assertNotIn(render_report.SITES_INCOMPLETE, complete)
        detail = next(entry for entry in data["responses"] if entry["tool"] == "get_control" and entry["response"]["control"].get("folders"))
        detail["response"]["control"]["folder_count"] = len(detail["response"]["control"]["folders"]) + 30
        page = render_report.render(data)["report.html"]
        self.assertIn("At least ", page)
        self.assertEqual(page.count(render_report.SITES_INCOMPLETE), 2)

    def test_kept_shares_keep_the_read_time_of_their_own_response(self):
        data = fixture()
        first = data["responses"][0]
        controls = first["response"]["controls"]
        with_shares = next(control for control in controls if control.get("kept_direct_shares"))
        other = next(control for control in controls if control["control_id"] != with_shares["control_id"])
        other["kept_direct_shares"] = [{"person": "Kai Morgan", "email": "kai.morgan@northwind-demo.com", "item_kind": "file", "item": "Plan.docx", "role": "Viewer"}]
        second = copy.deepcopy(first)
        second["arguments"] = {"from": "2025-11-01", "to": "2026-04-30"}
        second["response"]["kept_direct_shares_as_of"] = "2026-11-03T08:00:00Z"
        second["response"]["controls"] = [copy.deepcopy(with_shares)]
        data["responses"].insert(1, second)
        data["inputs"]["period"] = {"from": "2025-11-01", "to": "2026-10-31"}
        shares = rows_of(render_report.render(data)["shares.csv"])
        read_at = {row["folder_set"]: row["read_at"] for row in shares}
        self.assertEqual(read_at[with_shares["name"]], "2026-11-03 08:00 UTC")
        self.assertEqual(read_at[other["name"]], "2026-11-02 14:01 UTC")

    def test_refused_call_stops_the_render(self):
        data = copy.deepcopy(fixture())
        data["responses"][0]["response"] = {
            "refused": True, "reason": "administrator_required", "message": "Only administrators.",
        }
        with self.assertRaises(report_data.ReportDataError) as raised:
            render_report.render(data)
        self.assertIn("administrator_required", str(raised.exception))

    def test_folder_with_responses_loads_like_a_single_file(self):
        import tempfile

        data = fixture()
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "inputs.json"), "w", encoding="utf-8") as handle:
                json.dump(data["inputs"], handle)
            os.mkdir(os.path.join(directory, "responses"))
            for index, entry in enumerate(data["responses"]):
                with open(os.path.join(directory, "responses", f"{index:03d}.json"), "w", encoding="utf-8") as handle:
                    json.dump(entry, handle)
            self.assertEqual(render_report.render(report_data.load_data(directory)), self.files)


FIRST_CONTROL = "11111111-1111-4111-8111-111111111111"
EXTRACT_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
STORED_SHA256 = "3a7bd3e2360a3d29eea436fcfb7e44c735d117c42d1c1835420b6b9942dd4f1b"
EXTRACT_TOOLS = ("start_access_review_extract", "get_access_review_extract", "read_access_review_extract_rows")
FAILURE = "The extract did not finish in time. Start a new one."


def without_extract(data):
    """Drop every extract response, as when the server lists no extract tools."""
    data["responses"] = [entry for entry in data["responses"] if entry["tool"] not in EXTRACT_TOOLS]
    return data


def extract_responses(data, tool):
    return [entry for entry in data["responses"] if entry["tool"] == tool]


def fail_extract(data):
    """Replace the extract's completed responses with a failed one."""
    data["responses"] = [
        entry for entry in data["responses"]
        if entry["tool"] != "read_access_review_extract_rows"
        and not (entry["tool"] == "get_access_review_extract" and entry["response"]["status"] == "completed")
    ]
    data["responses"].append({
        "tool": "get_access_review_extract",
        "arguments": {"extract_id": EXTRACT_ID, "offset": 0},
        "response": {
            "extract_id": EXTRACT_ID, "status": "failed", "from": "2026-05-01", "to": "2026-10-31",
            "started_at": "2026-11-02T13:55:12Z", "finished_at": "2026-11-02T14:00:00Z", "failure_reason": FAILURE,
        },
    })
    return data


def without(data, tool, control_id=None, offset=None):
    """Drop the responses of one tool, for one control and one page when given."""
    def matches(entry):
        arguments = entry.get("arguments") or {}
        return (
            entry["tool"] == tool
            and (control_id is None or arguments.get("control_id") == control_id)
            and (offset is None or arguments.get("offset") == offset)
        )

    data["responses"] = [entry for entry in data["responses"] if not matches(entry)]
    return data


class CompletenessTest(unittest.TestCase):
    def assertRefused(self, data, *parts):
        with self.assertRaises(report_data.ReportDataError) as raised:
            render_report.render(data)
        for part in parts:
            self.assertIn(part, str(raised.exception))

    def test_a_missing_members_page_stops_the_render(self):
        data = without(fixture(), "list_control_members", FIRST_CONTROL, offset=2)
        self.assertRefused(data, "list_control_members", FIRST_CONTROL, "offset 2")

    def test_a_missing_evidence_page_stops_the_render(self):
        data = fixture()
        data["responses"][0]["response"]["next_offset"] = 3
        self.assertRefused(data, "get_access_review_evidence", "2026-05-01 to 2026-10-31", "offset 3")

    def test_a_gap_in_the_period_stops_the_render(self):
        data = fixture()
        data["responses"][0]["arguments"] = {"from": "2026-05-01", "to": "2026-08-31"}
        self.assertRefused(data, "get_access_review_evidence", "2026-09-01 to 2026-10-31")

    def test_an_evidence_range_outside_the_period_stops_the_render(self):
        data = fixture()
        data["responses"][0]["arguments"] = {"from": "2026-04-01", "to": "2026-10-31"}
        self.assertRefused(data, "get_access_review_evidence", "2026-04-01 to 2026-10-31", "outside the review period")

    def test_a_missing_control_detail_stops_the_render(self):
        data = without(fixture(), "get_control", FIRST_CONTROL)
        self.assertRefused(data, "get_control", FIRST_CONTROL)

    def test_missing_members_stop_the_render(self):
        data = without(fixture(), "list_control_members", FIRST_CONTROL)
        self.assertRefused(data, "list_control_members", FIRST_CONTROL)

    def test_missing_activity_stops_the_render(self):
        data = without(fixture(), "get_control_activity", FIRST_CONTROL)
        self.assertRefused(data, "get_control_activity", FIRST_CONTROL)

    def test_a_missing_activity_page_inside_the_period_stops_the_render(self):
        data = fixture()
        activity = next(entry for entry in data["responses"] if entry["tool"] == "get_control_activity")
        activity["response"]["entries"] = [item for item in activity["response"]["entries"] if item["at"] >= "2026-05-01"]
        activity["response"]["next_cursor"] = "page-2"
        self.assertRefused(data, "get_control_activity", FIRST_CONTROL, "cursor page-2")

    def test_activity_may_stop_once_entries_are_older_than_the_period(self):
        data = fixture()
        activity = next(entry for entry in data["responses"] if entry["tool"] == "get_control_activity")
        activity["response"]["next_cursor"] = "page-2"
        self.assertEqual(render_report.render(data), render_report.render(fixture()))


def section_three(page):
    return page.split('id="s3"', 1)[1].split("</section>", 1)[0]


def attachment_f(page):
    return page.split("<td>F</td>", 1)[1].split("</tbody>", 1)[0]


def google_fixture():
    """The Northwind fixture as a Google Workspace organization, with a Google group whose nested group differs."""
    data = fixture()
    data["inputs"]["data_source"] = "Google Workspace domain northwind.example, read by Polar Sky"
    for item in data["responses"]:
        if item["tool"] == "get_control":
            item["response"]["control"]["provider"] = "google_workspace"
        if item["tool"] == "get_access_review_extract" and item["response"]["status"] == "completed":
            integration = "99999999-9999-4999-8999-999999999999"
            item["response"]["groups"] = [
                {"integration_id": integration, "site_id": None, "group_id": "catalog@northwind.example",
                 "name": "Catalog", "kind": "google_group", "counted_members": 2, "provider_member_count": 2,
                 "nested_groups_match": False},
                {"integration_id": integration, "site_id": None, "group_id": "analysts@northwind.example",
                 "name": "Analysts", "kind": "google_group", "counted_members": 3, "provider_member_count": 4,
                 "nested_groups_match": False},
                {"integration_id": integration, "site_id": None, "group_id": "viewers@northwind.example",
                 "name": "Viewers", "kind": "google_group", "counted_members": 1, "provider_member_count": 1,
                 "nested_groups_match": True},
            ]
            item["response"]["groups_total"] = 3
    return data


class GoogleExtractTest(unittest.TestCase):
    def setUp(self):
        self.section = section_three(render_report.render(google_fixture())["report.html"])

    def test_section_three_says_the_extract_was_read_from_google_drive(self):
        self.assertIn("Polar Sky also read who has access live from Google Workspace at", self.section)
        self.assertIn(
            "<td>How the list was built</td><td>Polar Sky read each folder&#x27;s permissions live from Google Drive, "
            "and listed the members of every Google group they grant, nested groups included",
            self.section,
        )
        self.assertNotIn("Microsoft 365", self.section.replace("The folder has no Microsoft 365 id on record.", ""))

    def test_a_google_group_matches_only_when_every_group_nested_in_it_matches(self):
        self.assertIn(
            "3 groups counted. 1 matches Google Workspace&#x27;s own count. 2 differ: "
            "Catalog (a group nested in it differs or could not be read); "
            "Analysts (Polar Sky counted 3, Google Workspace reports 4).",
            self.section,
        )
        self.assertIn("compared the direct members it read with Google Workspace&#x27;s count of direct members", self.section)
        self.assertIn('<th class="n">Google Workspace&#x27;s count</th>', self.section)
        self.assertIn(
            '<td>Catalog</td><td>Google group</td><td class="n">2</td><td class="n">2</td>'
            "<td>Differs in a nested group</td>",
            self.section,
        )
        self.assertIn(
            '<td>Viewers</td><td>Google group</td><td class="n">1</td><td class="n">1</td><td>Matches</td>', self.section
        )


class MixedProviderExtractTest(unittest.TestCase):
    def test_an_extract_names_only_the_providers_it_read(self):
        data = fixture()
        for item in data["responses"]:
            if item["tool"] == "get_control" and item["response"]["control"]["id"].startswith("3333"):
                item["response"]["control"]["provider"] = "google_workspace"
            if item["tool"] == "get_access_review_extract" and item["response"]["status"] == "completed":
                item["response"]["exclusions"], item["response"]["exclusions_total"] = [], 0
        section = section_three(render_report.render(data)["report.html"])
        self.assertIn("Polar Sky also read who has access live from Microsoft 365 at", section)
        self.assertNotIn("live from Google Drive", section)

    def test_a_mixed_extract_names_both_providers_and_counts_against_each_groups_own(self):
        data = google_fixture()
        for item in data["responses"]:
            if item["tool"] == "get_control" and item["response"]["control"]["id"].startswith("1111"):
                item["response"]["control"]["provider"] = "microsoft365"
        section = section_three(render_report.render(data)["report.html"])
        self.assertIn("live from Google Workspace and Microsoft 365 at", section)
        self.assertIn("1 matches its provider&#x27;s own count.", section)
        self.assertIn('<th class="n">Provider&#x27;s count</th>', section)


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.files = render_report.render(fixture())
        self.page = self.files["report.html"]
        self.section = section_three(self.page)

    def test_section_three_shows_the_stored_file(self):
        self.assertIn("<td>Extract taken</td><td>2026-11-02 13:55 UTC</td>", self.section)
        self.assertIn(f"<code>{STORED_SHA256}</code>", self.section)
        self.assertIn("2,961 bytes", self.section)
        self.assertIn(
            "<td>Extract rows</td><td>6: grant 3, group member 2, link 1. From 3 folder sets and 3 folders read</td>",
            self.section,
        )
        self.assertIn("<td>Rows read</td><td>6, all in Attachment F</td>", self.section)
        self.assertIn("Yes. Polar Sky checked the whole stored file against this SHA-256", self.section)

    def test_section_three_says_how_the_extract_was_built_and_which_links_it_leaves_out(self):
        self.assertIn(
            "<td>How the list was built</td><td>Polar Sky read each folder&#x27;s permissions live from Microsoft 365", self.section
        )
        self.assertIn("<td>Link types not listed</td><td>The extract lists every link on the folders it read. Sharing links on files and subfolders", self.section)

    def test_a_group_count_that_differs_is_named(self):
        self.assertIn("1 differs: catalog-customer-data (Polar Sky counted 3, Microsoft 365 reports 4).", self.section)
        self.assertIn(
            '<td>catalog-customer-data</td><td>Entra group</td><td class="n">3</td><td class="n">4</td><td>Differs</td>',
            self.section,
        )
        self.assertIn(
            '<td>Catalog Members</td><td>SharePoint group</td><td class="n">5</td><td class="n"></td>'
            "<td>No count from Microsoft 365</td>",
            self.section,
        )

    def test_exclusions_are_listed_with_their_reason(self):
        self.assertIn(
            "<td>Model Eval Results</td><td>Catalog / Model Eval Results</td>"
            "<td>The folder has no Microsoft 365 id on record.</td>",
            self.section,
        )

    def test_rows_from_every_page_are_written_in_file_order_and_escaped(self):
        rows = rows_of(self.files["extract.csv"])
        self.assertEqual(
            [row["permission_id"] for row in rows], ["perm-1", "perm-1", "perm-1", "perm-2", "perm-3", "perm-4"]
        )
        self.assertEqual(rows[2]["principal_name"], "'+Formula Plus")
        self.assertEqual(rows[5]["roles"], "read; write")
        self.assertEqual(rows[3]["link_expires_at"], "2026-12-31 00:00 UTC")

    def test_attachment_f_lists_both_hashes(self):
        import hashlib

        attachment = attachment_f(self.page)
        csv_hash = hashlib.sha256(self.files["extract.csv"].encode("utf-8")).hexdigest()
        self.assertNotEqual(csv_hash, STORED_SHA256)
        self.assertIn(STORED_SHA256, attachment)
        self.assertIn(csv_hash, attachment)
        self.assertIn("so its SHA-256 differs from the stored file&#x27;s", attachment)
        self.assertIn('<td class="p"><code>', attachment)

    def test_a_failed_extract_is_reported_and_the_report_renders(self):
        files = render_report.render(fail_extract(fixture()))
        page = files["report.html"]
        self.assertNotIn("extract.csv", files)
        self.assertIn(f"<td>Extract</td><td>Failed: {FAILURE}</td>", section_three(page))
        self.assertIn(f"Not available. The extract failed: {FAILURE}", attachment_f(page))
        self.assertEqual({row["as_of"] for row in rows_of(files["members.csv"])}, {"2026-11-02 14:02 UTC"})

    def test_rendering_again_without_the_extract_removes_the_old_extract_csv(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            render_report.write_outputs(self.files, directory)
            self.assertTrue(os.path.exists(os.path.join(directory, "extract.csv")))
            render_report.write_outputs(render_report.render(fail_extract(fixture())), directory)
            self.assertFalse(os.path.exists(os.path.join(directory, "extract.csv")))
            self.assertTrue(os.path.exists(os.path.join(directory, "members.csv")))

    def test_rendering_again_removes_the_earlier_pdf(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            render_report.write_outputs(self.files, directory)
            with open(os.path.join(directory, "report.pdf"), "wb") as handle:
                handle.write(b"%PDF-1.7 old")
            render_report.write_outputs(self.files, directory)
            self.assertFalse(os.path.exists(os.path.join(directory, "report.pdf")))
            self.assertTrue(os.path.exists(os.path.join(directory, "report.html")))

    def test_a_mismatch_in_rows_or_hash_is_said_plainly(self):
        data = fixture()
        pages = extract_responses(data, "read_access_review_extract_rows")
        pages[-1]["response"]["rows"] = pages[-1]["response"]["rows"][:-1]
        pages[-1]["response"]["sha256"] = "00" * 32
        pages[0]["response"]["sha256_verified"] = False
        section = section_three(render_report.render(data)["report.html"])
        self.assertIn("This differs from the extract&#x27;s own row counts above.", section)
        self.assertIn("The row pages name a different SHA-256 than the stored file.", section)
        self.assertIn("No. Polar Sky did not confirm the stored file against this SHA-256", section)

    def test_the_last_extract_named_is_the_one_used(self):
        data = fixture()
        start = extract_responses(data, "start_access_review_extract")[0]
        earlier = copy.deepcopy(start)
        earlier["tool"] = "get_access_review_extract"
        earlier["response"].update({
            "extract_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd", "status": "failed", "failure_reason": "Earlier run.",
        })
        data["responses"].insert(data["responses"].index(start), earlier)
        self.assertEqual(render_report.render(data), self.files)


class ExtractCompletenessTest(unittest.TestCase):
    def assertRefused(self, data, *parts):
        with self.assertRaises(report_data.ReportDataError) as raised:
            render_report.render(data)
        for part in parts:
            self.assertIn(part, str(raised.exception))

    def test_a_running_extract_stops_the_render(self):
        data = fixture()
        data["responses"] = [
            entry for entry in data["responses"]
            if entry["tool"] not in EXTRACT_TOOLS or entry["response"]["status"] == "running"
        ]
        self.assertRefused(data, EXTRACT_ID, "get_access_review_extract", "completed or failed")

    def test_a_missing_rows_page_stops_the_render(self):
        data = fixture()
        data["responses"].remove(extract_responses(data, "read_access_review_extract_rows")[-1])
        self.assertRefused(data, "read_access_review_extract_rows", EXTRACT_ID, "cursor 1480")

    def test_missing_rows_stop_the_render(self):
        data = fixture()
        for entry in extract_responses(data, "read_access_review_extract_rows"):
            data["responses"].remove(entry)
        self.assertRefused(data, "read_access_review_extract_rows", EXTRACT_ID, "first page")

    def test_a_missing_groups_page_stops_the_render(self):
        data = fixture()
        completed = [
            entry for entry in extract_responses(data, "get_access_review_extract")
            if entry["response"]["status"] == "completed"
        ]
        completed[0]["response"]["next_offset"] = 25
        self.assertRefused(data, "get_access_review_extract", EXTRACT_ID, "offset 25")

    def test_an_extract_outside_the_period_stops_the_render(self):
        data = fixture()
        for entry in data["responses"]:
            if entry["tool"] in EXTRACT_TOOLS and "from" in entry["response"]:
                entry["response"]["from"] = "2026-04-01"
        self.assertRefused(data, EXTRACT_ID, "2026-04-01 to 2026-10-31", "outside the review period")


class RemovalRecordTest(unittest.TestCase):
    def render_with_records(self):
        data = fixture()
        control = data["responses"][0]["response"]["controls"][0]
        record = {
            "source": "removal_record", "action": "Remove a grant", "grantee_kind": "user",
            "principal": "Jordan Lee", "target": "/Shared/Catalog", "at": "2026-09-16T10:00:00Z",
            "checked_at": "2026-09-16T10:01:00Z",
        }
        control["removals"] = [
            dict(record, result="removed", confirmed_at="2026-09-16T10:01:00Z"),
            dict(record, result="failed", reason="Retention hold", confirmed_at=None),
            dict(record, result="pending", confirmed_at=None),
        ]
        control["kept_direct_shares"][0]["role"] = "writer"
        data["inputs"]["columns"] = {"removals": ["folder_set", "target_kind", "principal", "state", "confirmed_on"]}
        return render_report.render(data)

    def test_removal_records_are_counted_by_their_result(self):
        files = self.render_with_records()
        removals = rows_of(files["removals.csv"])
        self.assertEqual([row["state"] for row in removals], ["Removed", "Failed", "Pending"])
        self.assertEqual([row["target_kind"] for row in removals], ["Person", "Person", "Person"])
        self.assertEqual(removals[0]["confirmed_on"], "2026-09-16")
        self.assertIn("1 applied, 1 failed, 1 pending, 0 not applied.", files["report.html"])

    def test_the_table_and_the_summary_use_the_same_word_for_each_result(self):
        data = fixture()
        action = {"action": "Remove a grant", "step": "Remove Kai.", "target": "APAC", "at": "2026-09-16T10:00:00Z"}
        data["responses"][0]["response"]["controls"][0]["removals"] = [
            dict(action, state=state) for state in ("applied", "failed", "pending", "checked", "sending", "stale", "skipped")
        ]
        data["inputs"]["columns"] = {"removals": ["folder_set", "principal", "state"]}
        files = render_report.render(data)
        states = [row["state"] for row in rows_of(files["removals.csv"])]
        self.assertEqual([state.split(":")[0] for state in states],
                         ["Applied", "Failed", "Pending", "Pending", "Pending", "Not applied", "Not applied"])
        self.assertIn("1 applied, 1 failed, 3 pending, 2 not applied.", files["report.html"])
        self.assertIn("<tr><td>Pending</td><td>3</td></tr><tr><td>Not applied</td><td>2</td></tr>", files["report.html"])

    def test_not_applied_states_say_plainly_why_polar_sky_changed_nothing(self):
        data = fixture()
        action = {"action": "Remove a grant", "step": "Remove Kai.", "target": "APAC", "at": "2026-09-16T10:00:00Z"}
        data["responses"][0]["response"]["controls"][0]["removals"] = [
            dict(action, state=state) for state in ("stale", "skipped")
        ]
        data["inputs"]["columns"] = {"removals": ["folder_set", "principal", "state"]}
        states = [row["state"] for row in rows_of(render_report.render(data)["removals.csv"])]
        self.assertEqual(states, [
            "Not applied: the access had changed since Polar Sky prepared the removal, so Polar Sky left it as it was",
            "Not applied: Polar Sky left this change for the organization's own IT team to carry out",
        ])
        self.assertEqual([state for state in states if JARGON.search(state)], [])

    def test_removal_records_say_how_many_the_read_after_confirmed(self):
        page = self.render_with_records()["report.html"]
        self.assertIn("1 of 1 applied removals confirmed by the read after the removal", page)

    def test_a_lowering_record_is_named_lowered(self):
        data = fixture()
        data["responses"][0]["response"]["controls"][0]["removals"] = [{
            "source": "removal_record", "action": "Lower access", "grantee_kind": "user", "principal": "Jordan Lee",
            "target": "/Shared/Catalog", "result": "removed", "at": "2026-09-16T10:00:00Z",
            "confirmed_at": "2026-09-16T10:01:00Z",
        }]
        removals = rows_of(render_report.render(data)["removals.csv"])
        self.assertEqual([row["state"] for row in removals], ["Lowered"])
        self.assertIn("1 applied, 0 failed, 0 pending, 0 not applied.", render_report.render(data)["report.html"])

    def test_target_types_read_as_plain_words(self):
        data = fixture()
        record = {
            "source": "removal_record", "action": "Remove a grant", "principal": "Jordan Lee",
            "target": "/Shared/Catalog", "result": "removed", "at": "2026-09-16T10:00:00Z",
        }
        kinds = ["user", "group", "site_group", "domain", "anyone", "anonymous", "link", "shared_drive", "new_kind"]
        data["responses"][0]["response"]["controls"][0]["removals"] = [
            dict(record, grantee_kind=kind, at=f"2026-09-16T10:0{i}:00Z") for i, kind in enumerate(kinds)
        ]
        data["inputs"]["columns"] = {"removals": ["folder_set", "target_kind", "principal", "state"]}
        removals = rows_of(render_report.render(data)["removals.csv"])
        self.assertEqual([row["target_kind"] for row in removals], [
            "Person", "Group", "SharePoint group", "Domain", "Anyone with the link", "Anyone with the link",
            "Sharing link", "Shared drive", "New kind",
        ])

    def test_plan_actions_alone_leave_the_rescan_not_available(self):
        page = render_report.render(fixture())["report.html"]
        self.assertIn("Re-scan confirmation: not available in this version.", page)

    def test_kept_shares_name_provider_roles_like_the_member_lists(self):
        shares = rows_of(self.render_with_records()["shares.csv"])
        self.assertIn("Editor", [row["role"] for row in shares])


def activity_of(data, control_name):
    """Return the activity entries of the fixture control with the given name."""
    control_id = next(
        control["control_id"] for control in data["responses"][0]["response"]["controls"] if control["name"] == control_name
    )
    return next(
        response["response"]["entries"] for response in data["responses"]
        if response["tool"] == "get_control_activity" and response["arguments"]["control_id"] == control_id
    )


def changes_in_period(data, control_name):
    return {control["name"]: control for control in report_data.build_model(data)["controls"]}[control_name][
        "activity_in_period"
    ]


class ChangesInPeriodTest(unittest.TestCase):
    def test_every_audit_trail_event_type_is_counted(self):
        data = fixture()
        entries = activity_of(data, "Customer Records")
        entries.clear()
        for index, event_type in enumerate(sorted(report_data.AUDIT_TRAIL_EVENT_TYPES)):
            entries.append({"at": f"2026-07-{index + 1:02d}T10:00:00Z", "type": event_type, "actor": {"type": "system"}})
        self.assertEqual(changes_in_period(data, "Customer Records"), 11)

    def test_proposals_releases_and_other_entries_are_not_counted(self):
        data = fixture()
        entries = activity_of(data, "Customer Records")
        entries.clear()
        for event_type in ("proposal_proposed", "proposal_released", "proposal_dismissed", "delegated", None):
            entries.append({"at": "2026-07-01T10:00:00Z", "type": event_type, "actor": {"type": "system"}})
        self.assertEqual(changes_in_period(data, "Customer Records"), 0)

    def test_the_method_text_names_the_events_counted(self):
        page = render_report.render(fixture())["report.html"]
        self.assertIn("Changes in period counts the same events as the Polar Sky audit trail", page)
        self.assertIn("Polar Sky proposing access, or sending a proposal for review, is not counted.", page)


def controls_by_name(data):
    return {control["name"]: control for control in report_data.build_model(data)["controls"]}


class ApprovalEndedTest(unittest.TestCase):
    def setUp(self):
        self.files = render_report.render(fixture())
        self.page = self.files["report.html"]

    def test_a_carried_approval_turned_off_in_the_period_is_not_counted_as_approved(self):
        model = report_data.build_model(fixture())
        controls = {control["name"]: control for control in model["controls"]}
        self.assertEqual(controls["Model Eval Results"]["state"], report_data.CONTROL_ENDED)
        self.assertEqual(report_data.approval_text(controls["Model Eval Results"]), "Approved 2026-03-02, withdrawn 2026-10-19")
        self.assertEqual(model["totals"]["controls_approved_in_period"], 2)
        self.assertEqual(model["totals"]["controls_carried"], 0)
        self.assertIn(
            '<td>Model Eval Results<br><span class="cell-note">Approved 2026-03-02, withdrawn 2026-10-19</span></td>',
            self.page,
        )
        self.assertIn("<td>Customer Records</td>", self.page)
        self.assertIn(
            "1 folder set approved, then withdrawn: Model Eval Results, approved 2026-03-02, withdrawn 2026-10-19.", self.page
        )
        self.assertIn("3: 2 approved in the period; 1 approved, then withdrawn", self.page)

    def test_members_of_a_turned_off_control_kept_access_only_while_it_was_approved(self):
        members = {row["person_name"]: row for row in rows_of(self.files["members.csv"])}
        self.assertEqual(
            members["Omar Haddad"]["keeps_access"], "Yes, approved only until the approval was withdrawn 2026-10-19"
        )
        self.assertEqual(members["Leah Brooks"]["keeps_access"], "Yes")
        self.assertIn("2 of them had their access approved only until their folder set&#x27;s approval was withdrawn.", self.page)

    def test_a_member_decided_after_the_control_was_turned_off_is_not_said_to_have_kept_access(self):
        data = fixture()
        for response in data["responses"]:
            if response["tool"] == "list_control_members":
                for member in response["response"]["members"]:
                    if member["name"] == "Omar Haddad":
                        member["provenance"] = {"by": "user", "by_name": "Omar Haddad", "at": "2026-10-25T09:00:00Z"}
        files = render_report.render(data)
        members = {row["person_name"]: row for row in rows_of(files["members.csv"])}
        self.assertEqual(
            members["Omar Haddad"]["keeps_access"], "Added or changed 2026-10-25, after the approval was withdrawn 2026-10-19"
        )
        self.assertEqual(report_data.build_model(data)["totals"]["kept_until_ended"], 1)

    def test_an_approval_turned_off_and_approved_again_still_counts_as_approved(self):
        controls = controls_by_name(fixture())
        self.assertEqual(controls["Customer Records"]["state"], report_data.CONTROL_APPROVED)
        approvals = [row for row in rows_of(self.files["approvals.csv"]) if row["folder_set"] == "Customer Records"]
        self.assertEqual([row["ended"] for row in approvals], ["Withdrawn 2026-06-01", ""])

    def test_an_approval_made_in_the_period_and_turned_off_later_in_it(self):
        data = fixture()
        activity_of(data, "Catalog-Client-Viewers").append(
            {"at": "2026-10-19T15:00:00Z", "type": "proposal_reopened", "actor": {"type": "user", "name": "Dana Whitfield"}}
        )
        model = report_data.build_model(data)
        self.assertEqual(model["totals"]["controls_approved_in_period"], 1)
        page = render_report.render(data)["report.html"]
        self.assertIn("Access to 1 of 3 folder sets reviewed and approved 2026-08-04 to 2026-08-04.", page)
        self.assertIn(
            "2 folder sets approved, then withdrawn: Catalog-Client-Viewers, approved 2026-09-15, withdrawn 2026-10-19; "
            "Model Eval Results, approved 2026-03-02, withdrawn 2026-10-19.",
            page,
        )

    def test_an_upgrade_or_dismissal_ends_an_approval_in_its_own_words(self):
        for event_type, words in (("proposal_superseded", "replaced by a later approval"), ("proposal_dismissed", "rejected")):
            with self.subTest(event_type=event_type):
                data = fixture()
                activity_of(data, "Model Eval Results")[0]["type"] = event_type
                control = controls_by_name(data)["Model Eval Results"]
                self.assertEqual(report_data.approval_text(control), f"Approved 2026-03-02, {words} 2026-10-19")

    def test_an_end_after_the_period_leaves_the_approval_in_force(self):
        data = fixture()
        activity_of(data, "Model Eval Results")[0]["at"] = "2026-11-01T00:30:00Z"
        control = controls_by_name(data)["Model Eval Results"]
        self.assertEqual(control["state"], report_data.CONTROL_CARRIED)
        self.assertEqual(report_data.approval_text(control), "Approved 2026-03-02, before the period, still in force")

    def test_an_end_is_compared_as_a_time_not_as_text(self):
        data = fixture()
        activity_of(data, "Catalog-Client-Viewers").append(
            {"at": "2026-09-15T12:10:00-04:00", "type": "proposal_reopened", "actor": {"type": "system"}}
        )
        self.assertEqual(controls_by_name(data)["Catalog-Client-Viewers"]["state"], report_data.CONTROL_APPROVED)


def with_role_records():
    """Return the fixture with a lowering record and a removal record that name their roles."""
    data = fixture()
    data["responses"][0]["response"]["controls"][0]["removals"] += [
        {
            "source": "removal_record", "action": "Lower access", "grantee_kind": "user", "principal": "Priya Shah",
            "email": "priya.shah@northwind-demo.com", "target": "Catalog / Product Adoption / EMEA",
            "from_role": "write", "to_role": "read", "result": "removed", "at": "2026-09-16T08:05:00Z",
            "confirmed_at": "2026-09-16T08:06:00Z",
        },
        {
            "source": "removal_record", "action": "Remove a grant", "grantee_kind": "user", "principal": "Noah Kim",
            "email": "noah.kim@northwind-demo.com", "target": "Catalog / Product Adoption / APAC", "role": "write",
            "result": "removed", "at": "2026-09-16T08:06:00Z", "confirmed_at": "2026-09-16T08:07:00Z",
        },
    ]
    return data


def removals_by_principal(data):
    return {row["principal"]: row for row in rows_of(render_report.render(data)["removals.csv"])}


class RemovalRoleTest(unittest.TestCase):
    def setUp(self):
        self.removals = removals_by_principal(with_role_records())

    def test_a_lowering_shows_the_old_and_the_new_permission(self):
        self.assertEqual(self.removals["Priya Shah"]["role"], "Edit → Read")
        self.assertEqual(self.removals["Priya Shah"]["state"], "Lowered")

    def test_a_removal_record_shows_the_permission_it_took_away(self):
        self.assertEqual(self.removals["Noah Kim"]["role"], "Edit")

    def test_a_removal_without_role_fields_shows_as_before(self):
        self.assertEqual(self.removals["Jordan Lee"]["role"], "Viewer")
        data = with_role_records()
        for removal in data["responses"][0]["response"]["controls"][0]["removals"]:
            for key in ("role", "from_role", "to_role"):
                removal.pop(key, None)
        self.assertEqual([row["role"] for row in removals_by_principal(data).values()], ["", "", ""])

    def test_a_lowering_with_only_the_old_permission_shows_it(self):
        data = with_role_records()
        data["responses"][0]["response"]["controls"][0]["removals"][1].pop("to_role")
        self.assertEqual(removals_by_principal(data)["Priya Shah"]["role"], "Edit")

    def test_the_lowering_reaches_the_html_permission_column(self):
        page = render_report.render(with_role_records())["report.html"]
        self.assertIn("<td>Edit → Read</td>", page)


class WordingTest(unittest.TestCase):
    def test_basis_tags_are_shown_in_words(self):
        data = fixture()
        for response in data["responses"]:
            if response["tool"] == "list_control_members":
                for member in response["response"]["members"]:
                    if member["name"] == "Leah Brooks":
                        member["basis"] = "group_expansion"
                    if member["name"] == "Mia Novak":
                        member["basis"] = "new_tag"
        members = {row["person_name"]: row for row in rows_of(render_report.render(data)["members.csv"])}
        self.assertEqual(members["Leah Brooks"]["reason"], "Member of a group kept on the folders")
        self.assertEqual(members["Mia Novak"]["reason"], "New tag")
        self.assertTrue(members["Sam Ortiz"]["reason"].startswith("Presents APAC product adoption"))

    def test_an_acknowledgment_without_a_date_says_the_date_is_tbd(self):
        data = fixture()
        data["inputs"]["acknowledgment"].pop("date", None)
        page = render_report.render(data)["report.html"]
        self.assertNotIn("Information Security, .", page)
        self.assertIn("Ravi Menon, Vice President, Information Security, date TBD.", page)



def render_with_main(data):
    """Run the render command on a data file and return the output folder's files and what it printed."""
    import contextlib
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        data_path = os.path.join(directory, "data.json")
        with open(data_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        out = os.path.join(directory, "report")
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            status = render_report.main(["--data", data_path, "--out", out])
        files = {}
        for name in os.listdir(out):
            path = os.path.join(out, name)
            if os.path.isfile(path):
                with open(path, encoding="utf-8", newline="") as handle:
                    files[name] = handle.read()
        return status, files, printed.getvalue()


class ClockTest(unittest.TestCase):
    def test_the_render_command_stamps_generated_at_from_the_clock(self):
        from datetime import datetime, timedelta, timezone

        data = fail_extract(fixture())
        data["inputs"]["generated_at"] = "2099-01-01T00:00:00Z"
        before = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        status, files, _ = render_with_main(data)
        after = datetime.now(timezone.utc)
        self.assertEqual(status, 0)
        self.assertNotIn("2099-01-01", files["report.html"])
        stamped = {row["as_of"] for row in rows_of(files["members.csv"])}
        self.assertEqual(len(stamped), 1)
        stamped_at = datetime.strptime(stamped.pop(), "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        self.assertTrue(before - timedelta(minutes=1) <= stamped_at <= after)

    def test_a_data_folder_keeps_the_member_read_time_across_renders(self):
        import tempfile
        from datetime import datetime, timezone

        data = fail_extract(fixture())
        with tempfile.TemporaryDirectory() as directory:
            os.makedirs(os.path.join(directory, "responses"))
            with open(os.path.join(directory, "inputs.json"), "w", encoding="utf-8") as handle:
                json.dump(data["inputs"], handle)
            saved = 1_793_000_000
            for index, entry in enumerate(data["responses"], start=1):
                path = os.path.join(directory, "responses", f"{index:03d}-{entry['tool']}.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(entry, handle)
                os.utime(path, (saved + index, saved + index))
            last_members = max(
                saved + index for index, entry in enumerate(data["responses"], start=1) if entry["tool"] == "list_control_members"
            )
            expected = report_data.format_time(datetime.fromtimestamp(last_members, timezone.utc).isoformat())
            for generated_at in ("2026-11-12T08:00:00Z", "2026-11-20T08:00:00Z"):
                files = render_report.render(report_data.load_data(directory), generated_at=generated_at)
                self.assertEqual({row["as_of"] for row in rows_of(files["members.csv"])}, {expected})

    def test_the_render_command_needs_no_generated_at_in_the_inputs(self):
        data = fixture()
        del data["inputs"]["generated_at"]
        status, files, _ = render_with_main(data)
        self.assertEqual(status, 0)
        self.assertIn("by the Polar Sky compliance report skill", files["report.html"])


OVERFLOW_SCRIPT = (
    "<script>window.addEventListener('load', () => document.fonts.ready.then(() => {"
    "const wide = [];"
    "document.querySelectorAll('table').forEach((table) => {"
    "const section = table.closest('section');"
    "const right = section.getBoundingClientRect().right - parseFloat(getComputedStyle(section).paddingRight);"
    "const over = table.getBoundingClientRect().right - right;"
    "if (over > 0.5) { wide.push((table.previousElementSibling || {}).textContent + ' by ' + Math.round(over) + 'px'); }"
    "});"
    "document.body.setAttribute('data-overflow', wide.join(' | ') || 'none');"
    "}));</script>"
)


def all_columns(data):
    """Choose every column of every table the HTML shows with chosen columns."""
    definitions = report_data.load_reference("columns.json")
    data["inputs"]["columns"] = {
        table: [column["id"] for column in definitions[table]["columns"]] for table in ("groups", "shares", "removals")
    }
    return data


class TableWidthTest(unittest.TestCase):
    def test_a_table_with_more_than_eight_columns_is_marked_wide(self):
        page = render_report.render(all_columns(fixture()))["report.html"]
        removals = page.split("<h3>6.1 Removals</h3>", 1)[1]
        self.assertTrue(removals.lstrip().startswith('<table class="ps-table wide">'))
        default_shares = render_report.render(fixture())["report.html"].split("<h3>5.4 Kept direct shares</h3>", 1)[1]
        self.assertNotIn("wide", default_shares.split("<thead>", 1)[0])

    def test_every_table_fits_the_page_width_in_chrome(self):
        import make_pdf
        import re
        import subprocess
        import tempfile

        chrome = make_pdf.find_chrome()
        if not chrome:
            self.skipTest("No Chrome or Chromium to lay the report out.")
        for name, data in (("default columns", fixture()), ("every column", all_columns(fixture()))):
            with self.subTest(columns=name), tempfile.TemporaryDirectory() as directory:
                files = render_report.render(data)
                files["report.html"] = files["report.html"].replace("</body>", OVERFLOW_SCRIPT + "</body>")
                render_report.write_outputs(files, directory)
                profile = os.path.join(directory, "profile")
                laid_out = subprocess.run(
                    [chrome, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--window-size=1200,1000",
                     "--virtual-time-budget=5000", "--dump-dom",
                     "file://" + os.path.join(directory, "report.html")],
                    capture_output=True, text=True, timeout=120, check=False,
                )
                if laid_out.returncode != 0:
                    self.skipTest(f"Chrome could not start here (exit {laid_out.returncode}).")
                dumped = laid_out.stdout
                overflow = re.search(r'data-overflow="([^"]*)"', dumped)
                self.assertIsNotNone(overflow, "Chrome did not run the layout check")
                self.assertEqual(overflow.group(1), "none")


def summary_block(printed):
    """The summary lines the render command printed, without the leading dash."""
    block = printed.split("Summary, worded as the report states it:\n", 1)[1]
    return [line[2:] for line in block.splitlines()]


class SummaryTest(unittest.TestCase):
    def test_the_render_command_prints_the_summary_after_the_files(self):
        status, files, printed = render_with_main(fixture())
        self.assertEqual(status, 0)
        lines = summary_block(printed)
        self.assertIn("Access decisions: 10: 7 members, 2 kept direct shares and 1 removal in the period.", lines)
        self.assertIn("Folder sets: 3: 2 approved in the period; 1 approved, then withdrawn.", lines)
        self.assertIn("Removals: 1 applied, 0 failed, 0 pending, 0 not applied. Re-scan confirmation: not available in this version.", lines)
        self.assertIn("TBD: nothing.", lines)
        self.assertTrue(any(line.startswith("Extract: Taken 2026-11-02 13:55 UTC. SHA-256 " + STORED_SHA256) for line in lines))

    def test_every_summary_count_is_worded_as_the_html_states_it(self):
        model = report_data.build_model(fixture())
        page = render_report.render(fixture())["report.html"]
        for text in (render_report.decisions_text(model["totals"]), render_report.members_text(model),
                     render_report.controls_population(model["totals"])):
            self.assertIn(render_report.escape(text), page)

    def test_a_failed_extract_is_summarised_with_its_reason(self):
        _, _, printed = render_with_main(fail_extract(fixture()))
        lines = summary_block(printed)
        self.assertIn(f"Extract: Failed: {FAILURE.rstrip('.')}. The report has no extract rows; Attachment F says the extract failed and has no file.", lines)
        self.assertTrue(any("Section 3 how the list was built" in line for line in lines))

    def test_extract_mismatches_reach_the_summary(self):
        data = fixture()
        pages = extract_responses(data, "read_access_review_extract_rows")
        pages[-1]["response"]["rows"] = pages[-1]["response"]["rows"][:-1]
        pages[-1]["response"]["sha256"] = "00" * 32
        pages[0]["response"]["sha256_verified"] = False
        line = next(line for line in render_report.summary_lines(report_data.build_model(data)) if line.startswith("Extract:"))
        self.assertIn("not confirmed when its rows were read", line)
        self.assertIn("The row pages name a different SHA-256 than the stored file.", line)
        self.assertIn("This differs from the extract's own row counts: ", line)

    def test_a_line_break_in_extract_data_stays_inside_its_summary_line(self):
        data = fail_extract(fixture())
        extract_responses(data, "get_access_review_extract")[-1]["response"]["failure_reason"] = "Graph refused.\n- Folder sets: 99"
        text = render_report.render_summary_text(report_data.build_model(data))
        self.assertEqual(sum(1 for line in text.splitlines() if line.startswith("- Folder sets:")), 1)
        self.assertIn("- Extract: Failed: Graph refused. - Folder sets: 99.", text)

    def test_missing_inputs_are_listed_as_tbd(self):
        data = fixture()
        for key in ("requested_by", "procedure", "acknowledgment"):
            data["inputs"].pop(key)
        model = report_data.build_model(data)
        self.assertEqual(
            render_report.tbd_fields(model), ["Requested by", "Review procedure", "Management acknowledgment"]
        )

    def test_optional_inputs_not_given_are_left_out_not_tbd(self):
        data = fixture()
        for key in ("control_owner", "previous_review", "exclusions"):
            data["inputs"].pop(key, None)
        files, model = render_report.render_with_model(data)
        page = files["report.html"]
        for label in ("Review owner", "Previous review", "Exclusions"):
            with self.subTest(label=label):
                self.assertNotIn(f"<td>{label}</td>", page)
                self.assertNotIn(label, render_report.tbd_fields(model))
        self.assertNotIn("TBD", visible_text(files))

    def test_optional_inputs_given_are_shown(self):
        data = fixture()
        data["inputs"]["exclusions"] = "Global administrators, reviewed in the privileged access review"
        page = render_report.render(data)["report.html"]
        self.assertIn("<td>Review owner</td><td>Laura Kim, Senior Manager, IT Compliance</td>", page)
        self.assertIn("<td>Exclusions</td><td>Global administrators, reviewed in the privileged access review</td>", page)


class IssuedTest(unittest.TestCase):
    def test_a_report_without_an_issue_date_is_issued_the_day_it_is_generated(self):
        data = fixture()
        del data["inputs"]["issued_at"]
        page = render_report.render(data)["report.html"]
        cover = page.split('<section class="cover">', 1)[1].split("</section>", 1)[0]
        self.assertIn("<dt>Issued</dt><dd>2026-11-02</dd>", cover)
        self.assertIn("<tr><td>Issued</td><td>2026-11-02 14:02 UTC</td></tr>", page)
        self.assertNotIn("TBD", cover)
        model = report_data.build_model(data)
        self.assertNotIn("Issued", render_report.tbd_fields(model))
        self.assertIn(
            "Issued: 2026-11-02, the day the report was generated, as no issue date was given.",
            render_report.summary_lines(model),
        )

    def test_an_issue_date_the_person_gave_is_kept(self):
        page = render_report.render(fixture())["report.html"]
        self.assertIn("<dt>Issued</dt><dd>2026-11-03</dd>", page)
        self.assertIn("Issued: 2026-11-03.", render_report.summary_lines(report_data.build_model(fixture())))


LEAK = re.compile(r"\bNone\b|\bnull\b|\bnan\b|[{}]")


def visible_text(files):
    """The words a reader sees in the rendered files: the HTML without its style and logo, and every CSV."""
    texts = []
    for name, text in files.items():
        if name == "report.html":
            text = re.sub(r"<style>.*?</style>|<svg.*?</svg>", "", text, flags=re.S)
            text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
        texts.append(text)
    return "\n".join(texts)


def without_optional_values(data):
    """Drop every optional input and set optional fields Polar Sky may leave out to null."""
    data["inputs"] = {key: data["inputs"][key] for key in ("organization", "report_id", "framework", "period", "generated_at")}
    for entry in data["responses"]:
        response = entry["response"]
        if entry["tool"] == "get_control":
            for group in response["control"].get("kept_groups", []) + response["control"].get("dropped_groups", []):
                group["people_count"] = None
                group["email"] = None
        if entry["tool"] == "list_control_members":
            for member in response["members"]:
                for key in ("title", "department", "account_type", "role", "basis"):
                    member[key] = None
        if entry["tool"] in ("start_access_review_extract", "get_access_review_extract"):
            response["from"] = None
            response["to"] = None
            response["failure_reason"] = None
    return data


class MissingDataTest(unittest.TestCase):
    def test_a_failed_extract_shows_its_hash_as_not_available(self):
        page = render_report.render(fail_extract(fixture()))["report.html"]
        self.assertIn('<td>SHA-256 of extract</td><td><span class="na">Not available: the extract failed</span></td>', page)
        self.assertNotIn("None", visible_text({"report.html": page}))

    def test_missing_and_null_data_never_shows_none_or_a_placeholder(self):
        for name, data in (
            ("failed extract", fail_extract(fixture())),
            ("completed extract", without_optional_values(fixture())),
            ("failed extract, null fields", without_optional_values(fail_extract(fixture()))),
        ):
            with self.subTest(data=name):
                leaks = [line for line in visible_text(render_report.render(data)).splitlines() if LEAK.search(line)]
                self.assertEqual(leaks, [])

    def test_a_group_without_a_people_count_says_not_recorded(self):
        groups = rows_of(render_report.render(without_optional_values(fixture()))["groups.csv"])
        self.assertEqual({row["people_count"] for row in groups}, {"Not recorded"})

    def test_the_skill_fills_framework_placeholders_before_showing_a_default(self):
        with open(os.path.join(SKILL_DIRECTORY, "SKILL.md"), encoding="utf-8") as handle:
            skill = handle.read()
        self.assertIn("so they never see a placeholder", skill)


class SkillInstructionsTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SKILL_DIRECTORY, "SKILL.md"), encoding="utf-8") as handle:
            self.skill = handle.read()

    def test_the_skill_saves_results_with_the_write_tool_not_the_shell(self):
        self.assertIn("Save each file with your file Write tool", self.skill)
        self.assertIn("Never save a result through the shell", self.skill)

    def test_the_skill_leaves_generated_at_and_the_summary_to_the_render(self):
        self.assertIn("Leave out `generated_at`: the render stamps it from the clock.", self.skill)
        self.assertIn("The whole block, pasted word for word", self.skill)
        self.assertNotIn("Set `generated_at`", self.skill)

    def test_the_skill_reports_back_only_the_paths_the_block_and_the_reminder(self):
        self.assertIn("Your reply has only these three parts, in this order:", self.skill)
        self.assertIn('This sentence: "Read the report before you send it to your auditor."', self.skill)
        self.assertIn("Write nothing else: no other count, date, hash, name, reason or advice", self.skill)
        self.assertNotIn("Remind the person to read the report", self.skill)

    def test_the_skill_shows_one_list_per_table_with_each_default_checked(self):
        self.assertIn("one short list per table", self.skill)
        self.assertIn("each default column prefixed with `✓ ` and each optional column with no mark", self.skill)
        self.assertNotIn("with defaults marked", self.skill)


def read_no_folder(data):
    """Make the fixture's completed extract one that read no folder and holds no rows."""
    for page in extract_responses(data, "get_access_review_extract"):
        response = page["response"]
        if response.get("status") == "completed":
            response.update({"folders_read": 0, "rows": 0, "rows_by_kind": {}, "groups": []})
    for page in extract_responses(data, "read_access_review_extract_rows"):
        page["response"]["rows"] = []
    return data


class EmptyExtractTest(unittest.TestCase):
    def test_an_extract_that_read_no_folder_says_it_is_empty(self):
        data = read_no_folder(fixture())
        section = section_three(render_report.render(data)["report.html"])
        self.assertIn("but it read no folder, so the stored extract is empty. Section 3.2 lists what was left out and why.", section)
        self.assertNotIn("Polar Sky also read who has access live", section)
        self.assertNotIn("Polar Sky read each folder", section)
        self.assertIn("<td>Link types not listed</td><td><span class=\"na\">Not available: no folder was read</span></td>", section)
        line = next(line for line in render_report.summary_lines(report_data.build_model(data)) if line.startswith("Extract:"))
        self.assertIn("Polar Sky read no folder, so the extract is empty.", line)

    def test_an_extract_with_no_folder_in_scope_does_not_claim_a_failed_read(self):
        data = read_no_folder(fixture())
        for page in extract_responses(data, "get_access_review_extract"):
            page["response"]["exclusions"] = []
        section = section_three(render_report.render(data)["report.html"])
        self.assertIn("but no folder was in scope, so the stored extract is empty.", section)
        self.assertNotIn("Section 3.2 lists what was left out", section)
        line = next(line for line in render_report.summary_lines(report_data.build_model(data)) if line.startswith("Extract:"))
        self.assertIn("No folder was in scope, so the extract is empty.", line)

    def test_an_extract_with_exclusions_points_to_what_was_left_out(self):
        section = section_three(render_report.render(fixture())["report.html"])
        self.assertIn(". 3.2 lists what was left out and why</td>", section)

def empty_review(data):
    """Make the fixture an organization with no folder set in force in the period, as a first review of a new organization is."""
    data["responses"] = [
        entry for entry in data["responses"]
        if entry["tool"] not in ("get_control", "list_control_members", "get_control_activity")
    ]
    for entry in extract_responses(data, "get_access_review_evidence"):
        entry["response"].update({"controls": [], "total": 0})
    for page in extract_responses(data, "get_access_review_extract"):
        if page["response"].get("status") == "completed":
            page["response"].update({
                "controls": 0, "folders_read": 0, "rows": 0, "rows_by_kind": {}, "groups": [], "exclusions": [],
            })
    rows = extract_responses(data, "read_access_review_extract_rows")
    data["responses"] = [entry for entry in data["responses"] if entry not in rows[1:]]
    rows[0]["response"].update({"rows": [], "next_cursor": None})
    return data


class ProviderTest(unittest.TestCase):
    def test_no_provider_is_named_when_the_data_names_none(self):
        model = report_data.build_model(empty_review(fixture()))
        self.assertEqual(model["extract"]["providers"], [])
        files = render_report.render(empty_review(fixture()))
        text = visible_text(files).replace("Microsoft 365 tenant northwind-demo.onmicrosoft.com", "")
        self.assertNotIn("Microsoft 365", text)
        self.assertNotIn("Google", text)
        self.assertIn("Polar Sky started a live read of who has access at ", section_three(files["report.html"]))

    def test_a_sharepoint_group_row_names_microsoft_365(self):
        data = fixture()
        for item in data["responses"]:
            if item["tool"] == "get_control":
                item["response"]["control"].pop("provider", None)
            if item["tool"] == "get_access_review_extract":
                item["response"]["groups"] = []
        for page in extract_responses(data, "read_access_review_extract_rows"):
            for row in page["response"]["rows"]:
                row["control_id"] = None
        extract_responses(data, "read_access_review_extract_rows")[0]["response"]["rows"][0]["row_kind"] = "sharepoint_group_member"
        model = report_data.build_model(data)
        self.assertEqual(model["extract"]["providers"], ["microsoft365"])

    def test_a_group_of_an_unknown_kind_is_not_counted_against_microsoft_365(self):
        row = report_data._group_count_row({"name": "Finance", "kind": "other_group", "counted_members": 2})
        self.assertIsNone(row["provider"])
        self.assertEqual(row["result"], "No count from the provider")


NO_ACCESS_TO_REVIEW = (
    "Polar Sky recorded no folder sets with an access approval in force from 2026-05-01 to 2026-10-31, "
    "so there was no access to review."
)


class NoFolderSetsTest(unittest.TestCase):
    def setUp(self):
        self.files, self.model = render_report.render_with_model(empty_review(fixture()))
        self.page = self.files["report.html"]
        self.text = visible_text(self.files)
        self.lines = render_report.summary_lines(self.model)

    def test_the_report_says_once_that_there_was_no_access_to_review(self):
        self.assertEqual(self.text.count(NO_ACCESS_TO_REVIEW), 1)
        summary = self.page.split('id="s1"', 1)[1].split("</section>", 1)[0]
        self.assertIn(NO_ACCESS_TO_REVIEW, summary)
        self.assertEqual(self.lines[0], "Folder sets: " + NO_ACCESS_TO_REVIEW)

    def test_the_report_does_not_claim_a_review_happened(self):
        for claim in ("reviewed access to", "approved that access", "0 of 0", "for 0 folder sets", "Outcome of the",
                      "Polar Sky read everything in scope", "How the review was done", "Folder sets approved"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, self.text)

    def test_dependent_rows_say_there_is_nothing_rather_than_not_available(self):
        section = section_three(self.page)
        for row in ("<td>Folder sets</td><td>No folder sets</td>", "<td>Members at report time</td><td>No members</td>",
                    "<td>Kept direct shares</td><td>No kept direct shares</td>", "<td>Groups</td><td>No groups</td>",
                    "<td>Could not be read</td><td>Nothing: no folder was in scope</td>"):
            self.assertIn(row, section)
        self.assertIn("<td>Removals to verify</td><td>No removals</td>", self.page)
        self.assertNotIn("Confirmed by re-scan", self.page)
        self.assertNotIn("Within the deadline", self.page)
        self.assertIn("Removals: No removals.", self.lines)
        self.assertIn("People who approved access or added or changed it: no one.", self.lines)
        self.assertIn(
            "Not available in this version: Section 4 separate access rules; Section 5.5 site owners and applications; "
            "Section 7 exceptions.",
            self.lines,
        )

    def test_the_render_command_still_prints_the_block_to_paste(self):
        status, _, printed = render_with_main(empty_review(fixture()))
        self.assertEqual(status, 0)
        self.assertEqual(summary_block(printed)[0], "Folder sets: " + NO_ACCESS_TO_REVIEW)

    def test_nothing_reads_as_a_python_value(self):
        self.assertEqual([line for line in self.text.splitlines() if LEAK.search(line)], [])
        self.assertEqual([line for line in reader_words(empty_review(fixture())) if JARGON.search(line)], [])


class NoMembersTest(unittest.TestCase):
    def test_folder_sets_with_shares_but_no_members_do_not_claim_no_decisions(self):
        data = fixture()
        for entry in extract_responses(data, "list_control_members"):
            entry["response"].update({"members": [], "total": 0, "matching": 0, "next_offset": None})
        data["responses"] = [
            entry for entry in data["responses"]
            if not (entry["tool"] == "list_control_members" and (entry.get("arguments") or {}).get("offset"))
        ]
        model = report_data.build_model(data)
        self.assertGreater(model["totals"]["decisions"], 0)
        self.assertEqual(render_report.checklist_evidence(model, "who_decided"), "No members.")


class NoRemovalsTest(unittest.TestCase):
    def test_folder_sets_without_removals_do_not_call_the_re_scan_unavailable(self):
        data = fixture()
        for entry in extract_responses(data, "get_access_review_evidence"):
            for control in entry["response"]["controls"]:
                control["removals"] = []
        model = report_data.build_model(data)
        self.assertEqual(render_report.checklist_evidence(model, "removals"), "No removals.")
        self.assertFalse(any("re-scan" in part for part in render_report.not_available_parts(model)))


if __name__ == "__main__":
    unittest.main()


JARGON = re.compile(
    r"\bcontrols?\b|polic|delegat|reconcil|managed group|upgrade|turned off|\bplan\b|CLAUDE_CODE_SESSION_ID", re.IGNORECASE
)


def every_column(data):
    """Choose every column of every table, so each header and value is rendered."""
    definitions = report_data.load_reference("columns.json")
    data["inputs"]["columns"] = {table: [column["id"] for column in definition["columns"]] for table, definition in definitions.items()}
    return data


def framework_texts(framework):
    """The framework texts that may use the auditor's own word control, such as SOX IT general controls."""
    texts = [framework[key] for key in ("eyebrow", "subtitle", "control", "purpose", "requirement")]
    return texts + [item["requirement"] for item in framework["checklist"]]


def reader_words(data):
    """The words a reader sees in the report, its CSV files and the summary, without the framework's own texts."""
    files, model = render_report.render_with_model(data)
    text = visible_text(files) + "\n" + render_report.render_summary_text(model)
    for framework_text in sorted(framework_texts(model["framework"]), key=len, reverse=True):
        text = text.replace(render_report.fill(framework_text, render_report.fill_values(model)), "")
    return text.splitlines()


def mixed_fixture():
    data = google_fixture()
    for item in data["responses"]:
        if item["tool"] == "get_control" and item["response"]["control"]["id"].startswith("1111"):
            item["response"]["control"]["provider"] = "microsoft365"
    return data


def with_ending(data, event_type):
    activity_of(data, "Model Eval Results")[0]["type"] = event_type
    return data


def carried(data):
    activity_of(data, "Model Eval Results")[0]["at"] = "2026-11-01T00:30:00Z"
    return data


class NoPolarSkyJargonTest(unittest.TestCase):
    def test_the_report_never_calls_a_folder_set_a_control(self):
        variants = {
            "Microsoft 365": fixture, "Google Workspace": google_fixture, "mixed": mixed_fixture,
            "failed extract": lambda: fail_extract(fixture()),
            "replaced approval": lambda: with_ending(fixture(), "proposal_superseded"),
            "rejected approval": lambda: with_ending(fixture(), "proposal_dismissed"),
            "approved before the period": lambda: carried(fixture()),
        }
        for framework in report_data.load_reference("frameworks.json"):
            for name, build in variants.items():
                with self.subTest(framework=framework, data=name):
                    data = every_column(build())
                    data["inputs"]["framework"] = framework
                    data["inputs"]["review_interval"] = "Quarterly"
                    self.assertEqual([line for line in reader_words(data) if JARGON.search(line)], [])

    def test_the_csv_column_ids_name_folder_sets_not_controls(self):
        definitions = report_data.load_reference("columns.json")
        ids = [column["id"] for definition in definitions.values() for column in definition["columns"]]
        self.assertEqual([column_id for column_id in ids if "control" in column_id], [])
        self.assertIn("folder_set", ids)
        self.assertIn("reviewed_by", ids)
        self.assertIn("reviewed_on", ids)
        self.assertIn("folder_set_id", ids)
