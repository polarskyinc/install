# Webhook receivers other than Panther

**Tell the person:** Any receiver works if it accepts an https request from the internet and checks Polar Sky's signature. These are the settings to give it.

Read this page only for a receiver that is not Panther; Panther has its own steps in [Webhook endpoints](webhook.md#panther). Everything here comes from `signing` in the answer and from Polar Sky's webhook contract:

- Polar Sky sends one `POST` per notification, with `Content-Type: application/json` and one JSON object as the body. The log schema (`schema_url` in `panther`) describes the body's fields for any receiver.
- The header `X-Polar-Sky-Signature` holds `sha256=` followed by the lowercase hex HMAC with SHA 256 of the raw request body, keyed with the exact bytes of the signing secret. The receiver checks it over the bytes it received, before it parses the JSON, and compares in constant time.
- Any `2xx` answer within 15 seconds counts as accepted. A test notification makes one attempt. A real notification is tried again for up to 24 hours after `408`, `425`, `429`, any `5xx`, a timeout or a connection error, so a receiver may see one twice: it drops repeats by `event_id`.
- A receiver that cannot check signatures still needs a signing secret, because Polar Sky signs every notification. Its URL is then the only thing that keeps others out, so the person treats the URL as a secret.

If the person is building the receiver, offer to write the signature check for them, from these facts. The rules of [Webhook endpoints](webhook.md#the-url-and-the-secret-never-pass-through-you) still hold: you never read the file, so the code reads the secret from the receiver's own settings.
