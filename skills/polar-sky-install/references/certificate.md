# Phase 5: Engine certificate

The engine connects to Polar Sky Cloud with a client certificate. The private key is made on this machine and leaves it only into the cluster's Kubernetes secret. Never print it.

If `client.key` already exists in the install folder, do not make a new one without asking: a key may already be in use in the cluster. If `client.crt` exists too, go straight to [Check the certificate](#check-the-certificate).

## Make the key and the signing request

Show these, say they create `client.key` (secret) and `client.csr` (public) in the install folder, and run them after a yes:

```bash
cd ~/polar-sky-install && umask 077 && openssl genrsa -out client.key 2048 && chmod 600 client.key
```

```bash
cd ~/polar-sky-install && openssl req -new -key client.key -out client.csr -subj "/C=US/O=Polar Sky Inc/CN=${POLAR_SKY_ORGANIZATION_ID}"
```

Check the request (read only). It prints the subject and checks the signature:

```bash
cd ~/polar-sky-install && openssl req -in client.csr -noout -subject -verify
```

The subject must be `C=US, O=Polar Sky Inc, CN=` followed by the organization ID, and nothing else.

## Send only the CSR

Read `client.csr` with your file tool. It is public: a PEM block that starts with `-----BEGIN CERTIFICATE REQUEST-----`. Call `request_certificate` with that text as `certificate_signing_request`. Never pass `client.key`.

The answer is one of three:

| Answer | What to do |
| --- | --- |
| A signed certificate and a CA chain | Write the certificate to `client.crt` and the chain to `ca-chain.crt` in the install folder, exactly as given, with your file tool. Staff signing by hand send `client.crt` and `server-ca.crt`: save `server-ca.crt` as `ca-chain.crt`. Then check it, and tell the person in one line that Polar Sky signed the engine certificate and the date it expires (`not_after`). |
| Polar Sky staff will sign it | Tell the person Polar Sky staff will send `client.crt` to them. Stop this phase. When they have it, they save it as `~/polar-sky-install/client.crt` and tell you; then check it. You may go on with phase 6 up to the secrets. |
| A refusal | Show the reason. If it says the subject is wrong, make the request again with the subject above. For anything else, stop and tell the person to contact Polar Sky. |

## Check the certificate

The script reads `client.crt` and `client.key` in the install folder. It prints the certificate's subject, issuer and dates, checks the CN is the organization ID, and compares SHA-256 hashes of the public key in each file. It never prints the key.

```bash
cd ~/polar-sky-install && . ./values.env && <skill folder>/scripts/check-certificate.sh
```

It must end with `CERTIFICATE OK`. If the hashes differ, the certificate was made for another key: do not install it. Make a new key and request on this machine and send the new CSR.

Keep `client.key` and `client.crt` in the install folder for phase 6. If the person moves to another machine, make a new key and request there rather than copying the key.
