# Webhook endpoints: when it does not work

**Tell the person:** what the refusal or failure means and what to do next, in plain words, never a raw code.

Read this page from [Webhook endpoints](webhook.md#when-it-does-not-work) when a webhook step does not work. That page says when to call `report_issue`.

## When the upload is refused

| `reason` | What it means | What to do |
| --- | --- | --- |
| `upload_shape_invalid` | The file does not hold exactly two lines. | The person makes it the URL on line 1 and the secret on line 2, nothing else. Run the same command again. |
| `url_invalid` | Line 1 is not a URL Polar Sky can send to: it must start with `https://` and name a host on the internet, not an IP address or a local name such as `localhost`, and be at most 2048 characters. | The person copies the receiver's URL again onto line 1. Run the same command again. |
| `secret_invalid` | Line 2 is not a usable secret: 1 to 1024 characters, with no tabs or other control characters. | The person copies the secret again onto line 2. Run the same command again. |
| `wrong_content_type` | The command was changed. | Run the command exactly as `curl_command` gives it. |
| `upload_too_large` | The file holds more than a URL and a secret. | The person makes it two lines. Run the same command again. |
| `upload_token_expired`, `upload_too_many_attempts` or `upload_token_invalid` | The command expired, was tried too often, or was already used. | Call `start_webhook_connection` again with the same name for a new command. The file can stay as it is. |
| `not_an_administrator` | The person is no longer an administrator of the organization. | Stop. They ask an administrator of their organization in Polar Sky to do this. |
| `install_unavailable` | Polar Sky could not take the upload right now. | Wait a minute and run the same command again. |

## When Polar Sky refuses

| `reason` | What to do |
| --- | --- |
| `invalid_arguments` | The name must be 1 to 63 lowercase letters, digits or hyphens. Propose another. |
| `duplicate_name` | An endpoint already has this name. Agree another one with the person. |
| `endpoint_limit_reached` | The organization already has 5 endpoints. The person removes one on the Platform page first. |
| `secret_not_uploaded` | The upload has not run yet. Run the upload command, then save again. |
| `pending_connection_expired` or `pending_connection_not_found` | The hour ran out, or this one was already saved. Call `list_webhook_endpoints`; if the endpoint is not there, start again. |
| `pending_connection_started_by_another_administrator` | Another administrator started this upload. Start one of your own. |
| `invalid_url` or `invalid_secret` | Polar Sky refused the file when saving. Nothing was saved. The person fixes the file, and you start again. |
| `unknown_endpoint` | No endpoint has that name. Call `list_webhook_endpoints` and use one of its names. |
| `endpoint_disabled` | The endpoint is turned off. The person clicks **Enable** on it on the Platform page, then you test again. |
| `test_in_progress` | A test is already running. Wait a minute and call `list_webhook_endpoints` for its result. |
| `test_unavailable` or `install_unavailable` | Polar Sky could not do it right now. Try again in a minute. |
| `unknown_tool` | This Polar Sky does not offer the step in the conversation yet. Give the Platform page link, as in [When the person asks only for a webhook endpoint](webhook.md#when-the-person-asks-only-for-a-webhook-endpoint). |
| `not_an_administrator` or `account_inactive` | Stop. The person asks an administrator of their organization in Polar Sky to do this. |

## When the test fails

| `failure_reason` | Say | What to do |
| --- | --- | --- |
| `status`, with `last_status_code` 401 or 403 | The receiver answered that code: the signing secret does not match, or the header name or hash algorithm differ. | Check that the receiver uses the header `X-Polar-Sky-Signature` and SHA 256. If they match, the secrets differ: on the Platform page, **Edit** the endpoint and paste the receiver's secret, or put Polar Sky's secret into the receiver. Then test again. |
| `status`, with `last_status_code` 404 | The receiver answered 404: it does not know this URL. | A new Panther source may still be starting: [Webhook endpoints](webhook.md#upload-save-and-test) allows one retry a few minutes later. If it still fails, check the URL and **Edit** it on the Platform page. |
| `status`, another code | The receiver answered that code. | Check the receiver's settings against the ones it was given, then test again. |
| `timeout` | The receiver did not answer within 15 seconds. | Check that the receiver is running, then test again. |
| `dns` | The host name could not be found. | The URL is wrong. **Edit** it on the Platform page. |
| `tls` | A secure connection could not be made. | The receiver's certificate is not valid. Fix it in the receiver. |
| `connect` or `transport` | The receiver could not be reached, or the connection broke. | Check that the receiver accepts connections from the internet. If it only lets known senders in, the person asks their Polar Sky contact which addresses Polar Sky sends from. Then test again. |
| `address_refused` or `destination_invalid` | Polar Sky does not send to internal addresses, and this URL cannot receive notifications. | Use the receiver's public URL. **Edit** it on the Platform page. |
| `request` | Polar Sky could not build a request for this URL. | Check the URL and **Edit** it on the Platform page, then test again. |
| `endpoint_unavailable` | The endpoint was turned off or removed meanwhile. | Check the Platform page. |
| `expired` | Polar Sky stopped trying after 24 hours. | Check the receiver, then test again. |
| `unknown` | The delivery failed for a reason Polar Sky could not tell. | Test again. If it fails again, report it. |
