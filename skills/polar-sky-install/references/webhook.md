# Optional: webhook endpoints

**Tell the person:** A webhook endpoint sends Polar Sky's notifications to a tool the security team already watches, such as Panther. Each notification is signed, so the receiver can check that it came from Polar Sky.

Run this step only when the person asks for it: to add, list or test a webhook endpoint, or to check whether one works. It is the same in Cloud and On-Prem, and it can run during the install or long after it.

Ask one question at a time, and say in one line what happens next. Never say a tool name.

## When the person asks only for a webhook endpoint

Skip the preview, the questions and the install checks. Run only these, in order:

1. **The machine.** Run `uname -s` as [Machines that can run this](../SKILL.md#machines-that-can-run-this) says: macOS, Linux or WSL.
2. **The MCP server.** Check it as [Start](start.md#check-the-mcp-server) says. If `claude mcp list` shows `polar-sky-install` as needing authentication, tell the person to type `/mcp`, choose `polar-sky-install` and **Authenticate**. If they had to restart you, tell them to ask for the webhook endpoint again, not to say "Install Polar Sky".
3. **This Polar Sky offers the step.** If the tools have no `list_webhook_endpoints`, or a call answers `unknown_tool`, the person adds the endpoint in the console instead: call `get_install_values` (it only reads), give them its `console_url` followed by `/platform`, and tell them to use **Webhooks** there. Stop.
4. **The network.** Before you give any receiver step, run the network check in [Start](start.md#check-that-your-commands-can-reach-the-network) (it only reads). If your sandbox blocks the network, stop as Start says.
5. **curl.** The upload command needs curl 7.76 or later. Check with `curl --version` (it only reads). If it is older, tell the person to update curl first.

The first call that saves something, `start_webhook_connection`, may ask the person to approve write access. That is their choice; wait for it. If an answer says the person is not an administrator, or their account is not active, stop: they ask an administrator of their organization in Polar Sky to do this.

## What stays on the Platform page

Editing the URL or the secret, and **Enable**, **Disable** and **Remove** on an endpoint, stay on the Platform page. When the person asks for one of these, give them the link from `platform_url` in the answer of `list_webhook_endpoints`, and say where to click: the endpoint's row in the **Webhooks** card. You cannot do these for them.

## The URL and the secret never pass through you

The receiver's URL and its signing secret are credentials: some receivers carry their access in the URL. Both go in one file, `~/polar-sky-install/webhook-endpoint.txt`: the URL on line 1, the secret on line 2. They leave the machine only through the one-time upload command Polar Sky gives you.

- Never read, search or print `~/polar-sky-install/webhook-endpoint.txt` with any tool: no file reader, `cat`, `grep`, `head` or the like. Only the upload command reads it.
- The person edits the file in a plain text editor you are not connected to, such as TextEdit or Notepad, never in the editor they run you in. An editor such as VS Code, Cursor or a JetBrains IDE can attach the open file, or a selected line such as the secret, to the next chat message. Where a plain editor is certain, you may open the file in it for them; each of these returns at once and does not read the file:
  - macOS: `open -e ~/polar-sky-install/webhook-endpoint.txt` (always TextEdit).
  - WSL: `cmd.exe /c start "" notepad.exe "$(wslpath -w ~/polar-sky-install/webhook-endpoint.txt)"`
  - Linux: the person opens it themselves, never through you, because the desktop's default editor may be the one they run you in. They use a plain editor such as gedit or Kate, or `nano ~/polar-sky-install/webhook-endpoint.txt` in a terminal of their own.
- When you create the file, write it without reading it back.
- Never put the URL or the secret in the chat, a tool argument or a command argument, and never ask the person to paste them to you.
- If the person pastes the URL or the secret into the chat anyway, it is exposed: it stays in this conversation's history. Do not repeat it, use it or write it into the file for them. Tell them so, and with their yes start over with a new file and a new secret, and put the new secret in the receiver. If the pasted URL carries access, such as a token in its path, they also replace the URL in the receiver.
- No Polar Sky answer ever holds them: Polar Sky shows only the URL's host.

## See what is there

Call `list_webhook_endpoints` (it only reads). Tell the person which organization they are signed in to (`organization_name`), then, in plain words, for each endpoint:

- its name, the host it sends to, and whether it is turned on;
- its last delivery (`last_delivery`), the most recent notification sent to it: whether it was delivered, failed or is still being sent (`status`), when (`finished_at`, or `started_at` while it is being sent), whether it was a test (`event_type` `webhook.test`) or a real notification, and for a failure the reason in the words of [When the test fails](webhook-failures.md#when-the-test-fails).

If there are none, say so in one line. An organization can have at most 5 (`endpoint_limit`). At 5, adding one means removing one first, on the Platform page.

When the person only asked to list their endpoints or whether one works, answer and stop there. Then offer to send a test notification to an endpoint, and send it only after their yes.

## Choose the receiver and the name

Ask which tool should receive the notifications, and put the name in the same question, for example: "Which tool should receive Polar Sky's notifications? I'll call the endpoint `panther`; say if you want another name." The name is 1 to 63 lowercase letters, digits or hyphens, not used by an endpoint already listed, and cannot be changed later.

The receiver must be reachable from the internet at an https address with a host name: not an IP address, and not a local name such as `localhost`. Polar Sky does not send to internal addresses. If the receiver only lets known senders in, the person asks their Polar Sky contact which addresses Polar Sky sends from.

## Get the upload command

Call `start_webhook_connection` with the name. Nothing is saved yet. The answer holds `signing` (the settings the receiver checks), `panther` (Panther's settings and file links) and `curl_command` (the one-time upload command, valid until `expires_at`, one hour). If the answer is refused, see [When Polar Sky refuses](webhook-failures.md#when-polar-sky-refuses).

## Prepare the file

Create the file now, with this command (it only creates a new file in the install folder, so run it right after you show it). It puts a line to replace on line 1 and a new random signing secret on line 2, which is never shown:

```bash
umask 077 && command -v openssl > /dev/null && mkdir -p ~/polar-sky-install && set -o noclobber && { printf '%s\n' 'Replace this line with the receiver URL'; openssl rand -hex 32; } > ~/polar-sky-install/webhook-endpoint.txt && echo created
```

- It prints `created`: go on.
- It prints nothing: OpenSSL is missing, and nothing was made. The person installs OpenSSL, then you run the command again.
- It says the file exists: an earlier try left it. Recommend starting with a new one, unless the person was midway through setting up this same receiver with it. Delete it only after their yes, with `rm ~/polar-sky-install/webhook-endpoint.txt`, then run the command again.

## Set up the receiver

Open the file for them in a plain editor, as [above](#the-url-and-the-secret-never-pass-through-you), and give the steps for their receiver in one message: for Panther, the steps below; for any other receiver, read [Webhook receivers](webhook-receivers.md) and give what it says. In both:

- If the receiver asks for a secret, they copy line 2 of the file into it. If the receiver makes its own secret, they copy it over line 2.
- They put the receiver's URL on line 1, in place of the line to replace, and save the file.

End that message with the upload command from `curl_command` and: "When the file is saved, say go: I'll upload it to Polar Sky over an encrypted connection, save the endpoint, and send a test notification. If you'd rather test later, say so." For Panther, add that the test waits about five minutes after they say go, until Panther's new source is ready.

### Panther

These follow Panther's own guide for an HTTP source. The links come from `panther` in the answer.

1. **The log schema.** The person opens the schema file (`schema_url`) in their browser and copies everything from the line `fields:` to the end. In the Panther Console, they click **Schemas**, then **Create New**, enter `Custom.PolarSkyNotification` as the **Schema ID**, and in the **Schema** section click **Start** on the **Create your schema from scratch** tile. They paste into **Fields & Indicators**, click **Run Test**, then **Save**.
2. **The source.** They click **Log Sources**, then **Create New**, then the **HTTP** tile, enter a **Source Name**, such as `Polar Sky`, and choose `Custom.PolarSkyNotification` under **Schemas**.
3. For **Auth method**, they choose **HMAC**, enter `X-Polar-Sky-Signature` as the **Header Name** and choose **SHA 256** as the **Hashing Algorithm**.
4. For **Secret Key Value**, they paste line 2 of the file. If Panther makes the value itself, they copy Panther's value over line 2 of the file instead. Panther shows it only once.
5. They click **Setup**, copy the **HTTP Source URL** from the screen that follows onto line 1 of the file, and save the file.
6. Optional, so each notification raises an alert: they click **Detections**, then **Create New**, then **Start** on the **Python Rule** tile, enter `Polar Sky Notification` as the **Name**, choose `Custom.PolarSkyNotification` under **For the Following Source**, and paste the whole Python rule file (`rule_python_url`) into the editor under **Detect**. Under **Create Alert** they choose the severity **Info**; the rule gives each alert the notification's own severity. Under **Optional Fields** they set the **Deduplication Period** to 24 hours, then save the rule.

## Upload, save and test

The person's go says the file is saved and is the yes for the upload, the save and one test (Hard rule 1). If they said to test later, do the upload and the save only.

**Upload.** Run the command exactly as given. Never add `-v`, `--trace` or `--trace-ascii`, and never change the file name in it.

- It answers `uploaded` true: save.
- It answers a refusal: see [When the upload is refused](webhook-failures.md#when-the-upload-is-refused). After the person fixes the file, run the same command again. It works up to 5 times within the hour.
- It answers `upload_token_invalid` after the same command already answered `uploaded` true in this conversation: the file is already with Polar Sky. Save.

**Save.** Call `finish_webhook_connection` with the `pending_connection_id`. Polar Sky checks the URL and the secret again and saves the endpoint, turned on. Tell the person it is saved, with its name and the host it sends to (`destination_host`). The file stays until a test is delivered: it is the person's only copy of the URL and the secret, and the way to fix the endpoint.

**Wait for Panther.** The five minutes start when the person said go. Read the clock with `date +%H:%M`, tell them the time you will test, and wait in short sleeps, such as `sleep 60`, saying how long is left. Other receivers need no wait.

**Test.** Call `send_webhook_test` with the endpoint's name. It makes one attempt and waits up to 20 seconds.

- `delivered`: the receiver accepted it. For Panther, it shows in Panther's search under the log type `Custom.PolarSkyNotification`, which can take a few minutes.
- `failed`: tell the person why, from [When the test fails](webhook-failures.md#when-the-test-fails). If Panther answered `404`, its source may still be starting: test once more a few minutes later; the same go covers that one retry. Any other test needs a new yes.
- `pending`: tell the person "No answer yet; I'll check in a minute." Call `list_webhook_endpoints` every minute, up to three times. When the endpoint's last delivery has the same `event_id`, it is the test's result. When it has another one, a newer notification went out since: tell the person that delivery's result, which is how the endpoint does now. If it is still pending after three checks, say so, and that they can see the result later in the endpoint's last delivery on the Platform page, or by asking you to list their endpoints.

## Close

End with one message: the endpoint's name, the host it sends to, how the test went, and where to change it later, the Platform page (`platform_url`), in the **Webhooks** card. Only when a test was delivered, ask in the same message whether to delete `~/polar-sky-install/webhook-endpoint.txt`: Polar Sky keeps its own encrypted copy, and the receiver has the secret. Delete it only after their yes, with `rm ~/polar-sky-install/webhook-endpoint.txt`. When no test was delivered, tell them to keep the file for now.

## When it does not work

Read [Webhook endpoints: when it does not work](webhook-failures.md) for what each refusal and failure means and what to do. Tell the person both. Call `report_issue` with step `webhook` (as in [Report issues](../SKILL.md#report-issues)) only for an unexpected failure: one these pages do not expect, `install_unavailable` or `test_unavailable` that repeats, or a failure that stays after the fix. Do not report the one `404` retry for a new Panther source, a name already taken, a pending test or a file the person fixes and uploads again.
