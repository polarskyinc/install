"""The skill finds Polar Sky controls on either MCP server by the tool's name.

Run from the install repository root: python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-report/tests
"""

import os
import unittest

SKILL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SKILL.md")
TOOL = "get_access_review_evidence"


def skill_text():
    with open(SKILL_FILE, encoding="utf-8") as handle:
        return handle.read()


class ConnectionCheckTest(unittest.TestCase):
    def test_it_finds_the_tool_on_either_server(self):
        text = skill_text()
        self.assertIn("Find the connected server that lists `" + TOOL + "`, by the tool's name", text)
        self.assertIn("`mcp__polar-sky-controls__" + TOOL + "`", text)
        self.assertIn("`mcp__claude_ai_Polar_Sky_Controls__" + TOOL + "`", text)

    def test_it_uses_one_server_and_says_which_when_both_are_connected(self):
        text = skill_text()
        self.assertIn("Use that server for every tool call in this skill.", text)
        self.assertIn("If two servers list it, use the claude.ai connector, and tell the person in one line", text)

    def test_it_stops_when_no_server_lists_the_tool(self):
        self.assertIn(
            "If no connected server lists `" + TOOL + "`, say that Polar Sky controls are not connected and stop.",
            skill_text(),
        )

    def test_it_no_longer_needs_the_server_name(self):
        self.assertNotIn("Check that the `polar-sky-controls` MCP server is connected", skill_text())


if __name__ == "__main__":
    unittest.main()
