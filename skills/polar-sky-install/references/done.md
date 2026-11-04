# Phase 10: Done

**Tell the person:** Polar Sky now works on the locations the person chose: it finds overexposed files and proposes controls, and their team reviews and approves them in the Polar Sky console. Reviewing from their AI assistant works once Polar Sky turns it on for their organization.

## Hybrid

First run the pod checks from phase 6 again (read only). Say the install is done only if every check there passes.

If model pods still wait for GPU capacity, do not call the install complete. Say instead: "Everything is set up except the AI models, which are waiting for a free GPU machine in your cloud. They start on their own when one is free. Meanwhile the engine and Google Workspace are connected, and Polar Sky finds your files and who can open them, but it cannot judge how sensitive they are until the models run." Give the summary below with that line at the top, and offer to check the models again later.

If a model pod is not ready for another reason, say: "Everything is set up except the AI models, which are not running yet. Polar Sky cannot process documents until they do." Name the cause from phase 6, report it with `report_issue`, and give the summary below with that line at the top.

Give the person a short summary, with real values:

- **Runs in your cluster** (context, namespace `POLAR_SKY_NAMESPACE`): Flux, the Polar Sky chart version `POLAR_SKY_CHART_VERSION` on the `latest` channel, the two workers, the AI Gateway and the model servers on GPU nodes.
- **Google:** the service accounts `GOOGLE_ON_PREM_SERVICE_ACCOUNT` and `GOOGLE_CLOUD_SERVICE_ACCOUNT` in `GOOGLE_CLOUD_PROJECT_ID`, and their two delegation entries. Polar Sky keeps the cloud account's key, encrypted.
- **Certificate:** the subject and the end date from `scripts/check-certificate.sh`. It must be renewed before that date: run phase 5 again with a new key, and replace the `polar-sky-mtls` secret.
- **Okta** (only with Okta): the Okta org `OKTA_ORG_URL`, the app `Polar Sky Group Provisioning` with the Organization Administrator role, the start of Polar Sky's group names `OKTA_GROUP_PREFIX`, and how groups reach Google Workspace, in the words of phase 8. Polar Sky keeps the app's private key, encrypted; it never was on this machine.
- **Monitoring:** the locations the person chose in the console.
- **Checks skipped:** any preflight failure the person chose to accept, with their reason, if there was one.

## Cloud

There is no cluster, no engine and no AI model to check, so skip the pod checks. Say the install is done once the person has chosen the locations in the console.

Give the person a short summary, with real values:

- **Runs in Polar Sky Cloud:** the reading of Google Workspace, with the content scopes on the Polar Sky Cloud entry. Nothing runs in your cloud.
- **Google:** the service account `GOOGLE_CLOUD_SERVICE_ACCOUNT` in `GOOGLE_CLOUD_PROJECT_ID`, and its delegation entry with the scopes in `POLAR_SKY_CLOUD_SCOPES`. Polar Sky keeps the account's key, encrypted.
- **Okta** (only with Okta): the Okta org `OKTA_ORG_URL`, the app `Polar Sky Group Provisioning` with the Organization Administrator role, the start of Polar Sky's group names `OKTA_GROUP_PREFIX`, and how groups reach Google Workspace, in the words of phase 8. Polar Sky keeps the app's private key, encrypted; it never was on this machine.
- **Monitoring:** the locations the person chose in the console.

## What Polar Sky checks afterwards

Polar Sky's team checks the install on its own side, later and without the person.

- **Hybrid:** the workers read Google Workspace and process documents in the chosen locations, local inference and embedding work, and the results show in Polar Sky Cloud.
- **Cloud:** Polar Sky Cloud reads Google Workspace in the chosen locations, and the results show in Polar Sky Cloud. No models run in the customer's cloud, so there is no local inference to check.

Tell the person in one line that Polar Sky checks the install on its side and contacts them only if something needs their help. The person has nothing to arrange.

## Clean up the install folder

Ask the person before deleting anything. Suggest:

- Hybrid: move `on-prem-key.json` and `client.key` to their approved secrets store, or delete them: the cluster already holds them in the `gws-creds` and `polar-sky-mtls` secrets.
- Keep `values.env` for their records. In hybrid, also keep `client.crt` and the rendered files.
- With Okta: if `okta-admin-header` is still there, the Okta API token was not cleaned up. Ask the person to revoke the token in Okta (**Security** > **API** > **Tokens**) and delete the file, as in phase 8.
- Cloud: the key file is already deleted after the upload, so `values.env` is the only file to keep.

Hybrid only: remind them that Kubernetes secrets are only base64-encoded. Their cluster should encrypt secrets at rest, and only a few people should be able to read the Polar Sky namespace.
