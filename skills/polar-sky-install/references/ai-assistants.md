# AI assistants: authorize the ceiling checker

**Tell the person:** Polar Sky's AI assistants may never read more than the person they work for. Before each piece of work, Polar Sky asks Google Drive, as that person, whether that person can still open every approved folder. The account that asks is the ceiling checker. Polar Sky makes it for your organization alone, and it has no key. A Google Workspace super admin has to authorize it once in the Google Admin console. Until that is done, no AI assistant can be approved.

Run this step when the person wants AI assistants, or when `get_install_checklist` shows `ai_assistants` as `missing`. It comes after the install is done. It is for Google Workspace, in both models, and only where AI assistants are switched on for the organization. It does not depend on [helper identities](helper-identities.md): the two steps are separate, and either can come first.

You need a Google Workspace super admin for the Admin console. If the person is not one, ask who is, and offer to give that person the link and the steps below.

## Get the entry

Call `get_assistant_requirements`. The first call creates the organization's ceiling checker, so it can take up to a minute. It gives:

- `state`: `awaiting_authorization` or `verified`. When it is `verified`, tell the person AI assistants are ready to be approved, and stop;
- `delegation_client_id` and `delegation_scopes`: the entry to add. The scopes are one line, comma-separated, no spaces;
- `delegation_link`: a link that opens the Admin console's dialog with the client ID and scopes already filled in.

Give the person the link exactly as it was returned. Tell the person to open it while signed in as a super admin, check the client ID and the scopes, and click **Authorize**. If the link does not open the dialog, give the person the entry to add by hand under **Security** > **Access and data control** > **API controls** > **Domain-wide delegation** > **Manage all**.

Add this warning:

> **Important:** The link and an edit by hand both replace the entry's whole scope list. This client ID belongs to Polar Sky's ceiling checker, so its entry should hold exactly these scopes.

Google can take up to 24 hours to apply the entry, though it is often minutes.

## Check it

When the super admin says the entry is added, call `verify_assistant_delegation`. It takes no arguments. Polar Sky asks Google Drive, as the person you are talking to, who that person is, through the ceiling checker. It takes up to a minute.

When it answers `verified` true, tell the person the ceiling checker works and AI assistants can now be approved.

When it answers `verified` false, it gives Google's `reason`, and the `delegation_client_id`, `delegation_scopes` and `delegation_link` to correct the entry. Tell the person what Google said in plain words, give the link again, and call it again after the entry is fixed. If it fails again within a few minutes of a change, wait two minutes first: Google can take a while to apply it.

When it is refused, nothing was changed:

| `reason` | What it means | What to do |
| --- | --- | --- |
| `ai_assistants_not_available` | AI assistants are not switched on for this organization. | Tell the person Polar Sky has to switch them on first. Call `report_issue` with step `other` and outcome `blocked`. |
| `ai_assistants_need_google_workspace` | The organization has no Google Workspace connection. | Finish connecting Google Workspace as the install describes, then come back. |
| `no_email_address` | Polar Sky has no email address for the signed-in person. | Call `report_issue` with step `other` and outcome `blocked`. |
| `ai_assistant_worker_unavailable` | Polar Sky could not reach the service that sets up AI assistants. | Wait a minute and call again. If it keeps happening, call `report_issue` with step `other` and outcome `blocked`. |

Call `report_issue` with step `other` for any other refusal you cannot fix, as in [Report issues](../SKILL.md#report-issues).

## Finish

Tell the person, in plain words: the ceiling checker is authorized for the whole organization, AI assistants can be approved from now on, and approving one before this step is done is refused. Then go back to what the person was doing.
