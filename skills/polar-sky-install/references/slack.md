# Optional last step: connect Slack

**Tell the person:** Polar Sky sends some messages as Slack direct messages from the Polar Sky app, such as "controls are ready for review" and requests to file owners. Connecting Slack lets those messages reach people where they already work; without Slack, they get them by email.

Run this step only when the install plan has it: the person said in the questions that the company uses Slack and wants Polar Sky messages there. It is the same in Cloud and On-Prem. Run it last, after Google Workspace is connected and what Polar Sky monitors is saved, and before the summary in [Done](done.md). It is not needed for the install to work: when it is skipped or cannot finish, the install is still done.

Only a Polar Sky administrator can connect Slack, on the Platform page of the Polar Sky console. You cannot click for them, and you never get the app's token. You only give the link, explain, and check the result once.

This step only connects Slack. It does not choose which messages go to Slack. Requests that Polar Sky raises on its own stay email-only until an administrator turns Slack on in the console under **Controls** > **Settings**.

## When Slack is already connected

Call `get_install_values` with the same `deployment_model`. If it answers `slack_connected` true, Slack is already connected to the workspace in `slack_workspace_name`. Tell the person its name, and ask whether to keep it. If they want another workspace, say that changing it is not part of this install and needs Polar Sky support, and call `report_issue` with step `other`. Then go on to [Done](done.md).

If `slack_workspace_name` is null while `slack_connected` is true, say Slack is connected and ask the person which workspace they see on the Platform page.

## What the Polar Sky app may do in Slack

Slack shows this list when the person clicks Allow. Say it first, in these plain words, so nothing on Slack's page is a surprise:

- find people in the workspace by their work email, so a message reaches the right person;
- send people direct messages;
- read the messages people send to it;
- read messages and files in public channels it is added to.

It cannot read private channels or other people's direct messages.

## The step plan

Build the link from `console_url` in the answer of `get_install_values`, with `/platform` at the end, for example `https://app.polarsky.ai/platform`. Never give a link to `/api/slack/install`: a person who is not signed in gets an error there.

Show the plan in one message and ask "Does this look right?" One yes covers it:

1. Open `<console_url>/platform`, and sign in to Polar Sky if it asks.
2. Under **Available Integrations**, click **Connect** next to **Slack**.
3. In Slack, choose the company's workspace in the top right, and click **Allow**. If Slack asks for approval instead, send the request: the Slack admin gets it. When they approve it, click **Connect** on the Platform page again.
4. Tell me when it is done.
5. I check once that Polar Sky sees the workspace, and tell you its name.
6. You should get a direct message from the Polar Sky app in Slack, saying it is connected.

## Check the result

When the person says it is done, call `get_install_values` once, with the same `deployment_model`. Do not call it in a loop or before they say it is done: the person clicks in their browser, and you cannot see it.

- `slack_connected` true: tell the person Slack is connected to the workspace in `slack_workspace_name`, and that they should see the direct message from the Polar Sky app. If no message came, they can still go on; Polar Sky reaches them there when it has something to say.
- `slack_connected` false: ask what they saw in the browser, and match it to [When it does not work](#when-it-does-not-work). If they saw none of these, call `report_issue` with step `other` and outcome `blocked`, say that they can connect Slack later from the Platform page, and go on to [Done](done.md).

## When it does not work

For each case, call `report_issue` with step `other` (as in [Report issues](../SKILL.md#report-issues)), and tell the person what it means and what to do:

- **"This Slack connection link is no longer valid."** The link from Connect works for about a minute. Open the Platform page again and click **Connect** again. When it works, call `report_issue` again with outcome `resolved`.
- **"This Slack workspace is already connected to a different Polar Sky organization."** One Slack workspace can belong to only one Polar Sky organization. Only Polar Sky support can move it. Outcome `blocked`; go on to [Done](done.md).
- **Slack refuses an install for the whole Enterprise Grid organization.** Polar Sky does not support that. Click **Connect** again and choose one workspace, not the whole organization.
- **Slack says the app needs approval.** The person sends the request, and the Slack admin approves it in Slack. The install is done without it: they connect later from the Platform page, after the approval. Outcome `blocked`; go on to [Done](done.md).
