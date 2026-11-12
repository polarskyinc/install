# Polar Sky access reviews for Claude Code

Skills that turn the controls your data owners approved in Polar Sky into evidence for your auditor.

| Skill | What it does |
| --- | --- |
| [`access-review-report`](skills/access-review-report/README.md) | Builds an access review report (HTML, PDF and CSV files) for a date range, with a PCI DSS, SOC 2, HIPAA or SOX ITGC cover page |
| [`access-review-audit-trail`](skills/access-review-audit-trail/README.md) | Shows every change Polar Sky made to your controls in a date range, as a table and a CSV file |

The skills need the Polar Sky Controls connector, and an account that is a Polar Sky administrator or a named reviewer.

## Install

The Polar Sky install adds this plugin in Claude Code at the end. To add it yourself, run:

```bash
claude plugin marketplace add polarskyinc/install
claude plugin install polar-sky-access-reviews@polar-sky --scope user
```

Then ask Claude, in a new session: "Make an access review report for our auditor", or "Show the audit trail for September".

## Add a skill

Put a new skill in `skills/<skill name>/`, with its tests in `skills/<skill name>/tests/`, and add a row to the table above. `make test-plugin-skills` in Polar Sky's main repository runs every skill's tests.

Check the plugin with `claude plugin validate plugins/polar-sky-access-reviews`.
