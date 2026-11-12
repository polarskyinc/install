# Phase 6: Engine install

**Tell the person:** This installs the engine: the workers that find and read files, and the AI models that judge how sensitive each file is. It takes 20 to 30 minutes, mostly loading the models.

Installs the Kubernetes secrets, Flux, and the Polar Sky chart in the Polar Sky namespace. Before you start, phase 3 must have passed (or the person chose to skip the failures left), `client.crt` must have passed its check in phase 5, and `on-prem-key.json` must exist from phase 4. For Microsoft 365, in place of `on-prem-key.json`: the engine app's key file (`MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE`) must exist, and the engine app's check must have ended with `APP OK` ([Microsoft app registrations](microsoft-apps.md#check-the-app)), so a missing grant or a certificate that is not on the app is fixed before the key goes into the cluster. Run commands from the install folder.

Some commands below differ by provider: run the Google Workspace one or the Microsoft 365 one, never both. The engine reads one provider: for Microsoft 365, the chart gets no Google values, so Google Workspace stays off.

The Helm commands below pass values with `--set`, where a comma or `=` inside a value would add other chart values. Check the values again first (read only). It must end with `VALUES OK` and show a valid `GOOGLE_WORKSPACE_ADMIN_EMAIL`, or for Microsoft 365 valid `MICROSOFT_TENANT_ID`, `MICROSOFT_ON_PREM_APP_CLIENT_ID` and `MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE`; if not, stop:

```bash
. ~/polar-sky-install/values.env && <skill folder>/scripts/check-values.sh
```

## Check the target

```bash
kubectl config current-context && kubectl get nodes && helm list --namespace "${POLAR_SKY_NAMESPACE}"
```

Say which cluster this is. If this install built it, or the person named it in the install plan and the context matches, do not ask again; ask only if the context is a different cluster. If `helm list` shows `flux2` or `polar-sky` already, the install below upgrades it in place, which can replace its resources: that needs a separate yes.

## Show what will be installed

Flux and the Polar Sky chart create resources across the cluster. Render both and show the person a count of each kind of resource. The rendered files stay in the install folder for their security review; they are not printed.

```bash
helm repo add fluxcd-community https://fluxcd-community.github.io/helm-charts && helm repo update fluxcd-community
```

```bash
cd ~/polar-sky-install && umask 077 && helm template flux2 fluxcd-community/flux2 --version 2.17.2 --namespace="${POLAR_SKY_NAMESPACE}" --set installCRDs=true --set watchAllNamespaces=false --set helmController.create=true --set sourceController.create=true --set kustomizeController.create=false --set notificationController.create=false --set imageAutomationController.create=false --set imageReflectionController.create=false > flux-rendered.yaml && grep -E '^kind:' flux-rendered.yaml | sort | uniq -c
```

Google Workspace:

```bash
cd ~/polar-sky-install && umask 077 && helm template polar-sky "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set vllm.inferenceModelReplicas="${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}" --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set googleWorkspace.enabled=true --set googleWorkspace.secretName='gws-creds' --set googleWorkspace.adminEmail="${GOOGLE_WORKSPACE_ADMIN_EMAIL}" --set host="${POLAR_SKY_HOST}" > polar-sky-rendered.yaml && grep -E '^kind:' polar-sky-rendered.yaml | sort | uniq -c
```

Microsoft 365:

```bash
cd ~/polar-sky-install && umask 077 && helm template polar-sky "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set vllm.inferenceModelReplicas="${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}" --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set microsoft365.enabled=true --set microsoft365.secretName='microsoft365-credentials' --set host="${POLAR_SKY_HOST}" > polar-sky-rendered.yaml && grep -E '^kind:' polar-sky-rendered.yaml | sort | uniq -c
```

Tell the person, plainly:

- Flux adds cluster-wide custom resource definitions, cluster roles and cluster role bindings. Its helm-controller is bound to `cluster-admin` to manage the Polar Sky release. `watchAllNamespaces=false` limits what it watches, not what it may do.
- The `latest` channel installs new eligible Polar Sky releases by itself, and can move to a new minor version.
- The rendered files are in the install folder if their security team wants to review them.
- Only when `POLAR_SKY_INFERENCE_MODEL_REPLICAS` is set and not 3: the engine runs that many copies of the inference model, and the install first writes the count into the `polar-sky-customer-config` ConfigMap, so Flux keeps it.

This is the stage's plan. Ask: "Does this look right? Any changes, or shall I go ahead?" That one yes covers the namespace, the secrets, Flux, the customer ConfigMap and the Polar Sky chart below. Then run them in order, showing each command, and report each result in one line.

## Namespace

If it is missing (phase 3 normally created it), dry-run, then create:

```bash
kubectl create namespace "${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
kubectl create namespace "${POLAR_SKY_NAMESPACE}"
```

## Secrets

Check which already exist (names only, read only). Google Workspace:

```bash
kubectl get secret polar-sky-mtls gws-creds --namespace="${POLAR_SKY_NAMESPACE}" --ignore-not-found
```

Microsoft 365:

```bash
kubectl get secret polar-sky-mtls microsoft365-credentials gws-creds --namespace="${POLAR_SKY_NAMESPACE}" --ignore-not-found
```

If one exists, ask the person before replacing it: that is a separate yes. Never print its contents to compare. For Microsoft 365, `gws-creds` means the engine in this cluster was set up for Google Workspace, and Polar Sky connects one provider per organization: do not install over it. Tell the person, call `report_issue`, and stop.

The mTLS secret holds `client.crt` and `client.key`. Dry-run, then create:

```bash
cd ~/polar-sky-install && kubectl create secret tls polar-sky-mtls --cert=client.crt --key=client.key --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
cd ~/polar-sky-install && kubectl create secret tls polar-sky-mtls --cert=client.crt --key=client.key --namespace="${POLAR_SKY_NAMESPACE}"
```

The Google secret holds the on-premises JSON key, base64-encoded, as the engine expects. The key passes through a pipe only. Dry-run, then create:

```bash
base64 < "${GOOGLE_ONPREM_KEY_FILE}" | tr -d '\n' | kubectl create secret generic gws-creds --from-file=service-account-key=/dev/stdin --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
base64 < "${GOOGLE_ONPREM_KEY_FILE}" | tr -d '\n' | kubectl create secret generic gws-creds --from-file=service-account-key=/dev/stdin --namespace="${POLAR_SKY_NAMESPACE}"
```

For Microsoft 365, the Microsoft 365 secret takes the place of the Google one. It holds the engine app's three values under the names the chart reads: `client-id`, `tenant-id` and `certificate-base64`. The engine needs all three: without one, it turns Microsoft 365 off without an error. The certificate bundle, the engine app's private key and certificate, passes through a pipe only, base64-encoded as the engine expects. The two IDs are public. Each command first checks that the key file is there and not empty, and that both IDs are set; if one is missing, it stops before anything reaches the cluster, with no output: run the values check above. When `microsoft365-credentials` already exists, the create commands below would fail: keep it, or replace it as [Replace the Microsoft 365 secret](#replace-the-microsoft-365-secret) says, after its own yes. Otherwise dry-run, then create:

```bash
test -s "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -r "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -n "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" && test -n "${MICROSOFT_TENANT_ID}" && base64 < "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" | tr -d '\n' | kubectl create secret generic microsoft365-credentials --from-file=certificate-base64=/dev/stdin --from-literal=client-id="${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --from-literal=tenant-id="${MICROSOFT_TENANT_ID}" --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
test -s "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -r "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -n "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" && test -n "${MICROSOFT_TENANT_ID}" && base64 < "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" | tr -d '\n' | kubectl create secret generic microsoft365-credentials --from-file=certificate-base64=/dev/stdin --from-literal=client-id="${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --from-literal=tenant-id="${MICROSOFT_TENANT_ID}" --namespace="${POLAR_SKY_NAMESPACE}"
```

Each command prints only `secret/<name> created`. Never print a secret to check it.

## Install Flux

```bash
helm upgrade --install flux2 fluxcd-community/flux2 --version 2.17.2 --namespace="${POLAR_SKY_NAMESPACE}" --set installCRDs=true --set watchAllNamespaces=false --set helmController.create=true --set sourceController.create=true --set kustomizeController.create=false --set notificationController.create=false --set imageAutomationController.create=false --set imageReflectionController.create=false ${HELM_WAIT:---wait} --timeout 120s
```

## Fewer inference model copies

The engine runs 3 copies of the inference model. Only when the person asked for fewer ([Fewer copies of the inference model](cluster.md#fewer-copies-of-the-inference-model)), `values.env` has `POLAR_SKY_INFERENCE_MODEL_REPLICAS`. Never ask about the count here. Flux keeps the count only when it is in the ConfigMap `polar-sky-customer-config`, as `vllm.inferenceModelReplicas` in its `values.yaml`: a `--set` alone is undone by Flux's next update. So it goes there before the chart install. Run this section on every engine install, also with the default count: a ConfigMap from an earlier install may hold another count. The ConfigMap may already hold other settings of the person's, even the engine's API key (`vllm.apiKey`), so never print what it holds: show only the names of its top-level settings and the count line.

Below, the count is `POLAR_SKY_INFERENCE_MODEL_REPLICAS`, or 3 when it is not set. Check whether the ConfigMap exists (read only):

```bash
kubectl get configmap polar-sky-customer-config --namespace="${POLAR_SKY_NAMESPACE}" --ignore-not-found -o name
```

**It does not exist.** With the count 3, there is nothing to do. Otherwise dry-run, then create it:

```bash
printf 'vllm:\n  inferenceModelReplicas: %s\n' "${POLAR_SKY_INFERENCE_MODEL_REPLICAS}" | kubectl create configmap polar-sky-customer-config --from-file=values.yaml=/dev/stdin --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
printf 'vllm:\n  inferenceModelReplicas: %s\n' "${POLAR_SKY_INFERENCE_MODEL_REPLICAS}" | kubectl create configmap polar-sky-customer-config --from-file=values.yaml=/dev/stdin --namespace="${POLAR_SKY_NAMESPACE}"
```

**It exists.** Save what it holds to a private file in the install folder, and show only the names of its top-level settings and its count line (read only):

```bash
cd ~/polar-sky-install && umask 077 && kubectl get configmap polar-sky-customer-config --namespace="${POLAR_SKY_NAMESPACE}" -o jsonpath='{.data.values\.yaml}' > customer-config-values.yaml && grep -oE '^[A-Za-z0-9_.-]+:' customer-config-values.yaml; grep -E '^[[:space:]]+inferenceModelReplicas:' customer-config-values.yaml; grep -qE '^[[:space:]]*[{]' customer-config-values.yaml && echo "JSON values"
```

Then, by what it shows. When the ConfigMap has no count line, only the names are printed. A count already in the ConfigMap is the one the cluster runs, so it wins over `values.env`, unless the person asked for a new count in this conversation:

- **A count line with the count:** nothing to change.
- **A count line with another count, and the person did not ask for a new count in this conversation:** keep the ConfigMap's count, since someone set it on purpose, even when `values.env` holds another one from an earlier install. Do not ask. If it is 1, 2 or 3, write it into `values.env` as `export POLAR_SKY_INFERENCE_MODEL_REPLICAS='<count>'`, so the install passes the same count, and tell the person in one line how many copies run and that their ConfigMap sets it. Nothing to change. If it is another number, stop and report it with `report_issue`.
- **A count line with another count, and the person asked for the count in `values.env` in this conversation:** change the count in that line and keep the rest of the file:

  ```bash
  cd ~/polar-sky-install && umask 077 && sed -E "s/^([[:space:]]+inferenceModelReplicas:).*/\1 ${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}/" customer-config-values.yaml > customer-config-values.new && mv customer-config-values.new customer-config-values.yaml && grep -E '^[[:space:]]+inferenceModelReplicas:' customer-config-values.yaml
  ```

- **No count line, no top-level `vllm`, and no `JSON values` line:** with the count 3, nothing to change. Otherwise add the setting at the end of the file:

  ```bash
  cd ~/polar-sky-install && printf '\nvllm:\n  inferenceModelReplicas: %s\n' "${POLAR_SKY_INFERENCE_MODEL_REPLICAS}" >> customer-config-values.yaml
  ```

- **No count line, but a top-level `vllm` or a `JSON values` line:** with the count 3, nothing to change. Otherwise do not edit the file: you cannot see that setting, it may hold the API key, and a YAML line added to JSON values is ignored. Ask the person to add the line `inferenceModelReplicas: <count>` under `vllm`, at the same indent as the lines already under it (in JSON values, `"inferenceModelReplicas": <count>` inside `"vllm"`, adding `"vllm"` if it is not there), in their own terminal with `kubectl edit configmap polar-sky-customer-config --namespace=<namespace>`. When they are done, save and show it again with the command above, and check the count line. Skip the patch below.

When you changed the file, change only the ConfigMap's `values.yaml`, dry-run first. The change goes straight into `kubectl patch` through a pipe, so it is never printed, and the ConfigMap's other keys, labels and annotations stay as they are. Each prints only that the ConfigMap was patched:

```bash
cd ~/polar-sky-install && jq -n --rawfile values customer-config-values.yaml '{data: {"values.yaml": $values}}' | kubectl patch configmap polar-sky-customer-config --namespace="${POLAR_SKY_NAMESPACE}" --type merge --patch-file /dev/stdin --dry-run=server
```

```bash
cd ~/polar-sky-install && jq -n --rawfile values customer-config-values.yaml '{data: {"values.yaml": $values}}' | kubectl patch configmap polar-sky-customer-config --namespace="${POLAR_SKY_NAMESPACE}" --type merge --patch-file /dev/stdin
```

Never use `kubectl apply` or `kubectl replace` for it: `apply` would keep a copy of everything in the ConfigMap in an annotation, and `replace` would drop the ConfigMap's other keys, labels and annotations. At the end, whether or not anything changed, delete the saved file, since it may hold the API key:

```bash
rm -f ~/polar-sky-install/customer-config-values.yaml
```

## Install the Polar Sky chart

Dry-run against the cluster first. The output goes to a file, because it can hold rendered secrets; only the result is shown. Google Workspace:

```bash
cd ~/polar-sky-install && umask 077 && helm upgrade --install polar-sky "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set vllm.inferenceModelReplicas="${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}" --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set googleWorkspace.enabled=true --set googleWorkspace.secretName='gws-creds' --set googleWorkspace.adminEmail="${GOOGLE_WORKSPACE_ADMIN_EMAIL}" --set host="${POLAR_SKY_HOST}" --dry-run=server > polar-sky-dry-run.yaml && echo "dry run passed"
```

Microsoft 365:

```bash
cd ~/polar-sky-install && umask 077 && helm upgrade --install polar-sky "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set vllm.inferenceModelReplicas="${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}" --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set microsoft365.enabled=true --set microsoft365.secretName='microsoft365-credentials' --set host="${POLAR_SKY_HOST}" --dry-run=server > polar-sky-dry-run.yaml && echo "dry run passed"
```

If it passes, and for Microsoft 365 only, record the time from which Polar Sky counts this engine's reads, when `values.env` has no `POLAR_SKY_ENGINE_CONNECTED_AT` yet. The workers start reading as soon as they connect, so the time must come before the new workers' first read, and after the last read of any worker that ran before:

- **No Polar Sky release yet** (the target check's `helm list` showed no `polar-sky`): get it right before the install.
- **`polar-sky` already installed:** its workers are running and reading. Get it after the install instead, once both workers finished rolling out, with the wait command in [Replace the Microsoft 365 secret](#replace-the-microsoft-365-secret).

Get it with (read only):

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
```

Write it into `values.env` with your file tool, as `export POLAR_SKY_ENGINE_CONNECTED_AT='<the time>'`. From then on, every `get_install_values` call for Microsoft 365 passes it as `reading_since`, so only files this engine read count as read ([Connect Microsoft 365](microsoft365.md#confirm-polar-sky-started-reading)), and none that an earlier engine read.

Then install. Google Workspace:

```bash
helm upgrade --install polar-sky "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set vllm.inferenceModelReplicas="${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}" --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set googleWorkspace.enabled=true --set googleWorkspace.secretName='gws-creds' --set googleWorkspace.adminEmail="${GOOGLE_WORKSPACE_ADMIN_EMAIL}" --set host="${POLAR_SKY_HOST}" ${HELM_WAIT:---wait} --timeout 20m
```

Microsoft 365:

```bash
helm upgrade --install polar-sky "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set vllm.inferenceModelReplicas="${POLAR_SKY_INFERENCE_MODEL_REPLICAS:-3}" --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set microsoft365.enabled=true --set microsoft365.secretName='microsoft365-credentials' --set host="${POLAR_SKY_HOST}" ${HELM_WAIT:---wait} --timeout 20m
```

Add no other `--set` values. `vllm.inferenceModelReplicas` is the count in `polar-sky-customer-config` ([Fewer inference model copies](#fewer-inference-model-copies)), 3 when `POLAR_SKY_INFERENCE_MODEL_REPLICAS` is not set: Flux keeps the ConfigMap's count, and the `--set` makes the first install ask for the same number of GPUs. `host` is the Polar Sky Cloud endpoint from `get_install_values`, and `infraProfile` is the platform the person confirmed in phase 2. For Microsoft 365, the chart reads the three key names in `microsoft365-credentials` by default, so they need no value. It can take 20 minutes. Before you start it, tell the person this and that most of the time goes to loading the AI models. Run it in the background if your agent can, so you can check progress while it runs. If you cannot, ask the person to run it in their own terminal and tell you when it ends, and check progress meanwhile.

## Wait for the release and the pods

The release does not wait for the AI models. It shows `Ready` once Polar Sky has applied its configuration, even while model pods wait for a GPU node, and the model pods start on their own when one appears. So when the cloud has no GPU capacity yet, the model pods stay `Pending` and the install still succeeds.

Model weights can take 20 minutes to load. Do not wait in silence, and do not stop to wait for the person. Every two or three minutes, check the pods yourself with the pod list below (read only) and tell the person in one line what changed: for example "the workers are ready, 2 of 4 AI models are loading". If nothing changed, say so in a few words. If a pod stays `Pending` for more than a few minutes, look at its events at once (below) rather than waiting for the timeout: a zone without free GPUs shows there. Keep checking on your own until everything is ready or a check below fails. If your agent stops long commands, run this with `--timeout=9m` and repeat it up to three more times while it says it timed out:

```bash
kubectl wait helmrelease/polar-sky --for=condition=ready --timeout=30m --namespace="${POLAR_SKY_NAMESPACE}"
```

Then show the pods and where they run (read only):

```bash
kubectl get pods,deployments,persistentvolumeclaims --namespace="${POLAR_SKY_NAMESPACE}"
```

```bash
kubectl get pods --namespace="${POLAR_SKY_NAMESPACE}" -o custom-columns='POD:.metadata.name,NODE:.spec.nodeName,GPU:.spec.containers[*].resources.requests.nvidia\.com/gpu,READY:.status.containerStatuses[*].ready'
```

```bash
kubectl get nodes -l "<GPU label from the platform table in cluster.md>" -o custom-columns='NODE:.metadata.name,GPUS:.status.allocatable.nvidia\.com/gpu'
```

Check, and tell the person each result:

- [ ] The HelmRelease is `Ready`.
- [ ] Every worker and AI Gateway pod is ready.
- [ ] Every model-serving pod is ready on a node in the GPU node list, or `Pending` only because no GPU node is free yet (below).

If a worker or the AI Gateway is not ready, or a model pod fails for any other reason than GPU capacity, show the person the pod's events (read only, no secrets):

```bash
kubectl describe pod <pod name> --namespace="${POLAR_SKY_NAMESPACE}"
```

Name the cause you see (for example, an image it cannot pull) and stop. Do not change Polar Sky resources to work around it.

## Model pods waiting for GPU capacity

Look at a `Pending` model pod's events with `kubectl describe pod` (above). When they say the pod needs a GPU node that is not there, for example `FailedScheduling` with `Insufficient nvidia.com/gpu`, or that the cluster could not add one (`FailedScaleUp`, "out of resources"), and the GPU pool can still grow (it autoscales and is below its maximum, as the pool check in phase 3 shows), no GPU node is free yet. If the pool cannot grow, for example an existing cluster without GPU autoscaling or a pool at its maximum, the models will not start on their own: that is a failure, so name it and stop. Any other reason, such as an unbound PersistentVolumeClaim or an image it cannot pull, is a failure: name it and stop, as above. A GPU shortage does not stop the install: go on with phases 7 to 9. While the models wait, the workers run and connect to Polar Sky Cloud, and Polar Sky finds the files and who can open them. Judging how sensitive each file is waits for the models. Tell the person this plainly, naming Microsoft 365 in place of Google Workspace in a Microsoft 365 install: "The engine can connect and Google Workspace can be set up, but Polar Sky cannot judge how sensitive files are until the AI models run. They start on their own when a GPU machine is free."

Report the shortage once with `report_issue`, outcome `worked_around`. On GKE, run the instance group check from phase 3 ([GPU pool at zero](cluster.md#gpu-pool-at-zero)), and see [When GPU nodes cannot start](cluster.md#when-gpu-nodes-cannot-start). Keep checking the model pods while you go on, and tell the person when they start. Never call the install done or working while a model pod is not ready (phase 10).

## Change the number of inference model copies

Use it on an engine that is already installed, only when the person asks for fewer copies of the inference model ([Fewer copies of the inference model](cluster.md#fewer-copies-of-the-inference-model) says how to pick the count and what it costs), or to go back to the default 3 once the GPUs are there. The cluster must be able to run the copies plus one GPU nodes. Write the person's choice into `values.env` as `export POLAR_SKY_INFERENCE_MODEL_REPLICAS='<copies>'`, with `'3'` to go back. Changing the ConfigMap and asking Flux to apply it change Polar Sky's settings, so they need their own yes.

1. **Write the count into the ConfigMap,** as [Fewer inference model copies](#fewer-inference-model-copies) says.
2. **Ask Flux to apply it now.** This changes only an annotation on the HelmRelease:

   ```bash
   kubectl annotate helmrelease polar-sky --namespace="${POLAR_SKY_NAMESPACE}" --overwrite reconcile.fluxcd.io/requestedAt="$(date +%s)"
   ```

3. **Wait for the first update** (read only). Flux applies the count in two updates: the first writes it into the HelmRelease, and the second changes the inference model to it. Check every minute or so until this prints the new count:

   ```bash
   kubectl get helmrelease polar-sky --namespace="${POLAR_SKY_NAMESPACE}" -o jsonpath='{.spec.values.vllm.servingEngineSpec.modelSpec[?(@.name=="phi-4-mini")].replicaCount}'
   ```

   Then ask Flux again with the command in step 2, so the second update starts now.

4. **Confirm the inference model runs the new count** (read only). It must print the count:

   ```bash
   kubectl get deployment polar-sky-phi-4-mini-deployment-vllm --namespace="${POLAR_SKY_NAMESPACE}" -o jsonpath='{.spec.replicas}'
   ```

   Then check the model pods as in [Wait for the release and the pods](#wait-for-the-release-and-the-pods). New copies may wait for GPU nodes, as in [Model pods waiting for GPU capacity](#model-pods-waiting-for-gpu-capacity). If either count has not changed after 20 minutes, show the HelmRelease's conditions with the check in [A stalled release](#a-stalled-release), name the cause, and stop.

## A stalled release

A cluster installed with an older chart can end with the release stalled: the HelmRelease shows `Stalled=True` with the reason `MissingRollbackTarget`, and `Ready=False`. Flux does not retry a stalled release on its own. The workers keep running, but updates stop. Check (read only):

```bash
kubectl get helmrelease polar-sky --namespace="${POLAR_SKY_NAMESPACE}" -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
```

The fix is in the chart's README, in the section "Recover a stalled release". Read it from the chart itself (read only):

```bash
helm show readme "${POLAR_SKY_CHART_REFERENCE}" --version "${POLAR_SKY_CHART_VERSION}"
```

It patches the HelmRelease so the release no longer waits for pods and retries on failure, without remediation, then asks Flux to reconcile and reset its failure count. Offer it to the person, and show its commands with `"${POLAR_SKY_NAMESPACE}"` as the namespace. It changes a Polar Sky resource, so it needs its own yes. Do not wait for auto-update instead: a new chart revision can clear a stall by itself, but its first upgrade still runs under the old settings and waits 20 minutes again while model pods are `Pending`.

## Replace the Microsoft 365 secret

Microsoft 365 only. Use it to renew the engine app's certificate, which lasts two years, to replace a secret that already exists, or when the first reads show the secret is wrong. The workers read the secret only when they start, so replacing it also needs a restart of both. Report the reason with `report_issue` when it is a fix.

1. **For a renewal, a new certificate on the app first.** Make a new, dated certificate for the engine app and add it to the app, as [Microsoft app registrations](microsoft-apps.md#make-the-certificate) says, with that stage's yes, then run the engine app's check there with the new `MICROSOFT_ON_PREM_APP_CERTIFICATE`. It must end with `APP OK` before the new key goes into the cluster.
2. **Replace the secret in place,** after its own yes, from the key file in `MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE`. The new secret is rendered and goes straight into `kubectl replace` through a pipe: it is never printed, and the old secret stays until the new one is accepted. Dry-run first, then replace. Each prints only that the secret was replaced:

   ```bash
   test -s "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -r "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -n "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" && test -n "${MICROSOFT_TENANT_ID}" && base64 < "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" | tr -d '\n' | kubectl create secret generic microsoft365-credentials --from-file=certificate-base64=/dev/stdin --from-literal=client-id="${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --from-literal=tenant-id="${MICROSOFT_TENANT_ID}" --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=client -o yaml | kubectl replace --dry-run=server -f -
   ```

   ```bash
   test -s "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -r "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" && test -n "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" && test -n "${MICROSOFT_TENANT_ID}" && base64 < "${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE}" | tr -d '\n' | kubectl create secret generic microsoft365-credentials --from-file=certificate-base64=/dev/stdin --from-literal=client-id="${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --from-literal=tenant-id="${MICROSOFT_TENANT_ID}" --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=client -o yaml | kubectl replace -f -
   ```

   Never use `kubectl apply` for it: it would keep a copy of the secret's values in an annotation that `kubectl describe` shows.

3. **Restart both workers,** after its own yes. It changes the Polar Sky deployments only by starting new pods with the same settings:

   ```bash
   kubectl rollout restart deployment/polar-sky-document-discovery deployment/polar-sky-envelope-creation --namespace="${POLAR_SKY_NAMESPACE}"
   ```

4. **Wait for both** (read only):

   ```bash
   kubectl rollout status deployment/polar-sky-document-discovery --namespace="${POLAR_SKY_NAMESPACE}" --timeout=10m && kubectl rollout status deployment/polar-sky-envelope-creation --namespace="${POLAR_SKY_NAMESPACE}" --timeout=10m
   ```

5. **Check the new secret works.** Only once both rollouts finished, so no worker with the old secret runs any more, get the time with the `date` command in [Install the Polar Sky chart](#install-the-polar-sky-chart); do not write it into `values.env`. Run the worker check in [Engine connected](connection.md#microsoft-365-the-engine-app-in-the-workers), then confirm reading as [Confirm Polar Sky started reading](microsoft365.md#confirm-polar-sky-started-reading) says, with `reading_since` set to that time. The replacement is done only when `files_read` is above zero. Polar Sky reads again only what changed, so in a quiet tenant this can take longer than 15 minutes: then say so, report it, and offer to check again later. Once it is done, offer to delete the new key file, as [Delete the engine app's key file](microsoft365.md#delete-the-engine-apps-key-file) says, and for a renewal offer to remove the old certificate from the app, as in [Old certificates on a kept app](microsoft-apps.md#old-certificates-on-a-kept-app).
