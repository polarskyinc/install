# Phase 9: Done

Give the person a short summary, with real values:

- **Runs in your cluster** (context, namespace `POLAR_SKY_NAMESPACE`): Flux, the Polar Sky chart version `POLAR_SKY_CHART_VERSION` on the `latest` channel, the two workers, the AI Gateway and the model servers on GPU nodes.
- **Google:** the service accounts `GOOGLE_ON_PREM_SERVICE_ACCOUNT` and `GOOGLE_CLOUD_SERVICE_ACCOUNT` in `GOOGLE_CLOUD_PROJECT_ID`, and their two delegation entries. Polar Sky keeps the cloud account's key, encrypted.
- **Certificate:** the subject and the end date from `scripts/check-certificate.sh`. It must be renewed before that date: run phase 5 again with a new key, and replace the `polar-sky-mtls` secret.
- **Monitoring:** the locations the person chose in the console.

## What Polar Sky staff still do

- Add the organization to Polar Sky's model-serving allowlist (Nexus), if not done yet.
- Run the go-live checks with the person: the workers read Google Workspace and process an agreed test document inside a chosen location, local inference and embedding work, and the results show in Polar Sky Cloud.

Tell the person their Polar Sky contact will arrange these.

## Clean up the install folder

Ask the person before deleting anything. Suggest:

- Move `on-prem-key.json` and `client.key` to their approved secrets store, or delete them: the cluster already holds them in the `gws-creds` and `polar-sky-mtls` secrets.
- Keep `values.env`, `client.crt` and the rendered files for their records.

Remind them: Kubernetes secrets are only base64-encoded. Their cluster should encrypt secrets at rest, and only a few people should be able to read the Polar Sky namespace.
