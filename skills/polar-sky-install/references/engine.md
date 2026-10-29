# Phase 6: Engine install

Installs the Kubernetes secrets, Flux, and the Polar Sky chart in the Polar Sky namespace. Before you start, phase 3 must have passed and `client.crt` must have passed its check in phase 5. Run commands from the install folder.

The Helm commands below pass values with `--set`, where a comma or `=` inside a value would add other chart values. Check the values again first (read only). It must end with `VALUES OK` and show a valid `GOOGLE_WORKSPACE_ADMIN_EMAIL`; if not, stop:

```bash
. ~/polar-sky-install/values.env && <skill folder>/scripts/check-values.sh
```

## Check the target

```bash
kubectl config current-context && kubectl get nodes
```

Ask the person to confirm this is the approved cluster.

## Namespace

If it is missing (phase 3 normally created it), dry-run, then create after a yes:

```bash
kubectl create namespace "${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
kubectl create namespace "${POLAR_SKY_NAMESPACE}"
```

## Secrets

Check which already exist (names only, read only):

```bash
kubectl get secret polar-sky-mtls gws-creds --namespace="${POLAR_SKY_NAMESPACE}" --ignore-not-found
```

If one exists, ask the person before replacing it. Never print its contents to compare.

The mTLS secret holds `client.crt` and `client.key`. Dry-run, then create after a yes:

```bash
cd ~/polar-sky-install && kubectl create secret tls polar-sky-mtls --cert=client.crt --key=client.key --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
cd ~/polar-sky-install && kubectl create secret tls polar-sky-mtls --cert=client.crt --key=client.key --namespace="${POLAR_SKY_NAMESPACE}"
```

The Google secret holds the on-premises JSON key, base64-encoded, as the engine expects. The key passes through a pipe only. Dry-run, then create after a yes:

```bash
base64 < "${GOOGLE_ONPREM_KEY_FILE}" | tr -d '\n' | kubectl create secret generic gws-creds --from-file=service-account-key=/dev/stdin --namespace="${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
base64 < "${GOOGLE_ONPREM_KEY_FILE}" | tr -d '\n' | kubectl create secret generic gws-creds --from-file=service-account-key=/dev/stdin --namespace="${POLAR_SKY_NAMESPACE}"
```

Each command prints only `secret/<name> created`. Never print a secret to check it.

## Show what will be installed

Flux and the Polar Sky chart create resources across the cluster. Render both and show the person a count of each kind of resource. The rendered files stay in the install folder for their security review; they are not printed.

```bash
helm repo add fluxcd-community https://fluxcd-community.github.io/helm-charts && helm repo update fluxcd-community
```

```bash
cd ~/polar-sky-install && umask 077 && helm template flux2 fluxcd-community/flux2 --version 2.17.2 --namespace="${POLAR_SKY_NAMESPACE}" --set installCRDs=true --set watchAllNamespaces=false --set helmController.create=true --set sourceController.create=true --set kustomizeController.create=false --set notificationController.create=false --set imageAutomationController.create=false --set imageReflectionController.create=false > flux-rendered.yaml && grep -E '^kind:' flux-rendered.yaml | sort | uniq -c
```

```bash
cd ~/polar-sky-install && umask 077 && helm template polar-sky oci://us-docker.pkg.dev/polar-sky-public/charts/polar-sky-onprem --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set googleWorkspace.enabled=true --set googleWorkspace.secretName='gws-creds' --set googleWorkspace.adminEmail="${GOOGLE_WORKSPACE_ADMIN_EMAIL}" --set host="${POLAR_SKY_HOST}" > polar-sky-rendered.yaml && grep -E '^kind:' polar-sky-rendered.yaml | sort | uniq -c
```

Tell the person, plainly:

- Flux adds cluster-wide custom resource definitions, cluster roles and cluster role bindings. Its helm-controller is bound to `cluster-admin` to manage the Polar Sky release. `watchAllNamespaces=false` limits what it watches, not what it may do.
- The `latest` channel installs new eligible Polar Sky releases by itself, and can move to a new minor version.
- The rendered files are in the install folder if their security team wants to review them.

Wait for a yes before installing.

## Install Flux

```bash
helm upgrade --install flux2 fluxcd-community/flux2 --version 2.17.2 --namespace="${POLAR_SKY_NAMESPACE}" --set installCRDs=true --set watchAllNamespaces=false --set helmController.create=true --set sourceController.create=true --set kustomizeController.create=false --set notificationController.create=false --set imageAutomationController.create=false --set imageReflectionController.create=false ${HELM_WAIT:---wait} --timeout 120s
```

## Install the Polar Sky chart

Dry-run against the cluster first. The output goes to a file, because it can hold rendered secrets; only the result is shown:

```bash
cd ~/polar-sky-install && umask 077 && helm upgrade --install polar-sky oci://us-docker.pkg.dev/polar-sky-public/charts/polar-sky-onprem --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set googleWorkspace.enabled=true --set googleWorkspace.secretName='gws-creds' --set googleWorkspace.adminEmail="${GOOGLE_WORKSPACE_ADMIN_EMAIL}" --set host="${POLAR_SKY_HOST}" --dry-run=server > polar-sky-dry-run.yaml && echo "dry run passed"
```

Then, after the person says yes:

```bash
helm upgrade --install polar-sky oci://us-docker.pkg.dev/polar-sky-public/charts/polar-sky-onprem --version "${POLAR_SKY_CHART_VERSION}" --namespace "${POLAR_SKY_NAMESPACE}" --set organization.id="${POLAR_SKY_ORGANIZATION_ID}" --set certificate.secretName='polar-sky-mtls' --set vllm.enabled=true --set releaseChannel="${POLAR_SKY_RELEASE_CHANNEL}" --set infraProfile="${POLAR_SKY_INFRA_PROFILE}" --set googleWorkspace.enabled=true --set googleWorkspace.secretName='gws-creds' --set googleWorkspace.adminEmail="${GOOGLE_WORKSPACE_ADMIN_EMAIL}" --set host="${POLAR_SKY_HOST}" ${HELM_WAIT:---wait} --timeout 20m
```

Add no other `--set` values. `host` is the Polar Sky Cloud endpoint from `get_install_values`, and `infraProfile` is the platform the person confirmed in phase 2. It can take 20 minutes. If your agent stops commands after a time limit, run it in the background, or ask the person to run it in their own terminal and tell you when it ends.

## Wait for the release and the pods

Model weights can take 20 minutes to load. If your agent stops long commands, run this with `--timeout=9m` and repeat it up to three more times while it says it timed out:

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
kubectl get nodes -l "<GPU label from the profile table in cluster.md>" -o custom-columns='NODE:.metadata.name,GPUS:.status.allocatable.nvidia\.com/gpu'
```

Check, and tell the person each result:

- [ ] The HelmRelease is `Ready`.
- [ ] Every worker, AI Gateway and model-serving pod is ready.
- [ ] Every pod that asks for an NVIDIA GPU runs on a node in the GPU node list.

If something is not ready, show the person the pod's events (read only, no secrets):

```bash
kubectl describe pod <pod name> --namespace="${POLAR_SKY_NAMESPACE}"
```

Name the cause you see (for example, an image it cannot pull, or no GPU node to schedule on) and stop. Do not change Polar Sky resources to work around it.
