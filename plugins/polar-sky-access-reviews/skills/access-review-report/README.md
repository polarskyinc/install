# access-review-report

Builds the Polar Sky access review report from the controls MCP. `SKILL.md` is what Claude follows; this page is for people working on the skill.

## Layout

| Path | What it holds |
|---|---|
| `SKILL.md` | The steps Claude follows |
| `references/frameworks.json` | Cover page, requirement and checklist text for each framework |
| `references/columns.json` | The columns of each table, with defaults |
| `references/data-schema.md` | The data folder the renderer reads |
| `scripts/report_data.py` | Reads the data and derives rows and counts |
| `scripts/render_report.py` | Writes `report.html` and the CSV files (Python 3 standard library, no network; the command stamps `generated_at` from the clock) |
| `scripts/make_pdf.py` | Prints the HTML to PDF with local headless Chrome or Chromium |
| `assets/report.css`, `assets/wordmark.svg` | Taken from the sample report in PR #1947 |
| `assets/fonts/` | Sora and JetBrains Mono, see below |
| `tests/` | Fixture, golden files and tests |

## Run by hand

```sh
python3 scripts/render_report.py --data tests/fixtures/northwind.json --out /tmp/access-review
python3 scripts/make_pdf.py --html /tmp/access-review/report.html
```

`make_pdf.py` looks for Chrome, Chromium or Edge in `/Applications` on macOS and on `PATH` on Linux (`google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `microsoft-edge`). Set `CHROME_PATH` or pass `--chrome` for another place. With no browser it exits with 3 and says how to print from a browser.

## Test

From the root of the install repository (`install-skill/` in Polar Sky's main repository, where `make test-plugin-skills` runs it in CI):

```sh
python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-report/tests
```

After an intended change to the output, rewrite the golden files and check the diff:

```sh
UPDATE_GOLDEN=1 python3 -m unittest discover -s plugins/polar-sky-access-reviews/skills/access-review-report/tests
git diff plugins/polar-sky-access-reviews/skills/access-review-report/tests/golden
```

## Summary

After the file paths, `render_report.py` prints a block that starts with `Summary, worded as the report states it:`: the folder sets, access decisions, members, removals, kept direct shares, the extract, what is not available and what is TBD, in the report's own words. The skill gives it to the person word for word, so Claude never counts or adds.

## Extract

The skill starts a live read of who has access (`start_access_review_extract`) right after it asks for the inputs, polls `get_access_review_extract` until it completes or fails, and then reads every page of groups, exclusions and rows. Section 3 shows the stored file's SHA-256, its size, the row counts by kind, each group's member count next to the provider's own count (for Google Workspace, the direct members of the group and of every group nested in it), what could not be read and whether the SHA-256 was checked. Attachment F lists the stored file and `extract.csv` with a SHA-256 each; they differ because the CSV is a rendering of the stored file. A failed extract is reported as failed and the rest of the report renders; with no extract tools on the server, the report marks the extract "Not available in this version".

## CSV escaping

A CSV cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a single quote in front, so a spreadsheet does not run it as a formula (OWASP CSV injection guidance). The HTML shows the value unchanged.

## Fonts

Bundled so the PDF looks the same everywhere and no font is fetched from the network. Both are under the SIL Open Font License 1.1; the license sits next to each font.

| Font | Files | License | Source |
|---|---|---|---|
| Sora | Regular, Medium, SemiBold, Bold | OFL 1.1, `assets/fonts/sora/OFL.txt` | Copyright 2019 The Sora Project Authors, https://github.com/sora-xor/sora-font (copied from the Polar Sky brand-guidelines skill) |
| JetBrains Mono | Regular, Medium | OFL 1.1, `assets/fonts/jetbrains-mono/OFL.txt` | Copyright 2020 The JetBrains Mono Project Authors, https://github.com/JetBrains/JetBrainsMono (copied from the Polar Sky brand-guidelines skill) |

The renderer copies `assets/fonts/` next to `report.html`; keep the two together when you move the HTML.
