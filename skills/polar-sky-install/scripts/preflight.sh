#!/usr/bin/env bash
# Checks the current Kubernetes cluster against the Polar Sky profile and reports every failure at once with its fix; creates only short-lived test pods it deletes.
set -u

namespace="${POLAR_SKY_NAMESPACE:-}"
profile="${POLAR_SKY_INFRA_PROFILE:-}"
polar_sky_host="${POLAR_SKY_HOST:-connect.polarsky.ai:443}"
test_namespace="polar-sky-preflight-$(date +%s)"
test_namespace_created=0
busybox_image="busybox:1.36.1"
curl_image="curlimages/curl:8.10.1"

failures=0
warnings=0

pass() { printf 'PASS  %s\n' "$1"; }

fail() {
  printf 'FAIL  %s\n      fix: %s\n' "$1" "$2"
  failures=$((failures + 1))
}

warn() {
  printf 'WARN  %s\n      note: %s\n' "$1" "$2"
  warnings=$((warnings + 1))
}

finish() {
  printf '\n'
  if [ "${failures}" -eq 0 ]; then
    printf 'PREFLIGHT PASSED (%d warning(s))\n' "${warnings}"
    exit 0
  fi
  printf 'PREFLIGHT FAILED: %d failure(s), %d warning(s)\n' "${failures}" "${warnings}"
  exit 1
}

if [ -z "${namespace}" ] || [ -z "${profile}" ]; then
  printf 'Load values.env first: POLAR_SKY_NAMESPACE and POLAR_SKY_INFRA_PROFILE (from phase 2) must be set.\n'
  exit 2
fi

case "${profile}" in
  gke)
    gpu_selector="cloud.google.com/gke-accelerator=nvidia-l4"
    gpu_taint="nvidia.com/gpu=*:NoSchedule"
    storage_class=""
    model_host="storage.googleapis.com"
    ;;
  eks)
    gpu_selector="workload-type=gpu,gpu-type=t4"
    gpu_taint="nvidia.com/gpu=*:NoSchedule"
    storage_class="efs-polarsky-retain"
    model_host="huggingface.co"
    ;;
  aks)
    gpu_selector="accelerator=nvidia"
    gpu_taint="sku=gpu:NoSchedule"
    storage_class="premium-azurefile-retain"
    model_host="huggingface.co"
    ;;
  *)
    printf 'POLAR_SKY_INFRA_PROFILE must be gke, eks or aks.\n'
    exit 2
    ;;
esac

cleanup() {
  if [ "${test_namespace_created}" -eq 1 ]; then
    kubectl delete namespace "${test_namespace}" --ignore-not-found --wait=false >/dev/null 2>&1
  fi
  kubectl delete pod polar-sky-egress-check --namespace "${namespace}" --ignore-not-found --wait=false >/dev/null 2>&1
}
trap cleanup EXIT

check_cluster() {
  local context server_version minor
  context="$(kubectl config current-context 2>/dev/null)"
  if [ -z "${context}" ]; then
    fail "kubectl has no current context" "point kubectl at the approved cluster (the recipe's credentials command, or your usual one)"
    finish
  fi
  if ! kubectl get namespace kube-system --request-timeout=15s >/dev/null 2>&1; then
    fail "kubectl cannot reach the cluster of context ${context}" "sign in to the cloud CLI again, or check the network path to the cluster"
    finish
  fi
  server_version="$(kubectl version 2>/dev/null | sed -n 's/^Server Version: //p')"
  minor="$(printf '%s' "${server_version}" | sed -n 's/^v1\.\([0-9][0-9]*\).*/\1/p')"
  if [ -z "${minor}" ]; then
    warn "context ${context}, Kubernetes version unknown (${server_version:-no answer})" "Polar Sky needs Kubernetes 1.33 or newer; check the version with your cloud console"
  elif [ "${minor}" -lt 33 ]; then
    fail "context ${context}, Kubernetes ${server_version} is older than 1.33" "upgrade the cluster to Kubernetes 1.33 or newer"
  else
    pass "context ${context}, Kubernetes ${server_version}"
  fi
}

check_nodes() {
  local name os arch bad=0 nodes
  if ! nodes="$(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.operatingSystem}{"\t"}{.status.nodeInfo.architecture}{"\n"}{end}' 2>/dev/null)" || [ -z "${nodes}" ]; then
    fail "could not list the cluster's nodes" "you need permission to list nodes (kubectl get nodes); a cluster administrator grants it"
    return
  fi
  while IFS="$(printf '\t')" read -r name os arch; do
    [ -n "${name}" ] || continue
    if [ "${os}" != "linux" ] || [ "${arch}" != "amd64" ]; then
      fail "node ${name} is ${os}/${arch}" "Polar Sky runs only on Linux amd64 nodes; remove this node, or agree with Polar Sky how to keep Polar Sky pods off it"
      bad=1
    fi
  done <<EOF
${nodes}
EOF
  [ "${bad}" -eq 1 ] || pass "every node is Linux amd64"
}

check_gpu_nodes() {
  local name gpus taints total=0 count=0 gpu_nodes
  if ! gpu_nodes="$(kubectl get nodes -l "${gpu_selector}" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\t"}{range .spec.taints[*]}{.key}={.value}:{.effect};{end}{"\n"}{end}' 2>/dev/null)"; then
    fail "could not list the GPU nodes" "you need permission to list nodes (kubectl get nodes); a cluster administrator grants it"
    return
  fi
  while IFS="$(printf '\t')" read -r name gpus taints; do
    [ -n "${name}" ] || continue
    count=$((count + 1))
    case "${gpus}" in
      '' | 0) fail "GPU node ${name} has no allocatable nvidia.com/gpu" "install or repair the NVIDIA driver and device plugin on this node" ;;
      *) total=$((total + gpus)) ;;
    esac
    case ";${taints}" in
      *";"${gpu_taint}";"*) ;;
      *) fail "GPU node ${name} lacks the taint ${gpu_taint}" "add the taint to the GPU pool, as the ${profile} profile needs" ;;
    esac
  done <<EOF
${gpu_nodes}
EOF
  if [ "${count}" -eq 0 ]; then
    warn "no GPU nodes with label ${gpu_selector} right now" "fine if the GPU pool scales from zero; check the pool's settings as cluster.md says. Otherwise label the GPU nodes as the ${profile} profile needs"
  elif [ "${total}" -lt 4 ]; then
    warn "${total} allocatable GPU(s) on ${count} GPU node(s) now" "the model fleet needs 4; fine if the pool can grow to 4"
  else
    pass "${total} allocatable GPUs on ${count} GPU node(s)"
  fi
}

check_storage_class() {
  if [ -z "${storage_class}" ]; then
    pass "no StorageClass needed for the ${profile} profile"
  elif kubectl get storageclass "${storage_class}" >/dev/null 2>&1; then
    pass "StorageClass ${storage_class} exists"
  else
    fail "StorageClass ${storage_class} is missing" "create it as the ${profile} profile needs (the EKS recipe creates it); it must support ReadWriteMany"
  fi
}

can_i() {
  local answer
  answer="$(kubectl auth can-i "$@" 2>/dev/null | head -n 1)"
  [ "${answer}" = "yes" ]
}

check_permissions() {
  local resource missing=""
  for resource in customresourcedefinitions.apiextensions.k8s.io clusterroles.rbac.authorization.k8s.io clusterrolebindings.rbac.authorization.k8s.io namespaces; do
    can_i create "${resource}" || missing="${missing} ${resource}"
  done
  for resource in deployments.apps services serviceaccounts secrets configmaps networkpolicies.networking.k8s.io poddisruptionbudgets.policy roles.rbac.authorization.k8s.io rolebindings.rbac.authorization.k8s.io persistentvolumeclaims pods; do
    can_i create "${resource}" --namespace "${namespace}" || missing="${missing} ${resource}(${namespace})"
  done
  if ! can_i bind clusterroles/cluster-admin && ! can_i '*' '*' --all-namespaces; then
    missing="${missing} bind-cluster-admin"
  fi
  if [ -z "${missing}" ]; then
    pass "you can install Flux and the Polar Sky chart"
  else
    fail "you cannot create:${missing}" "a cluster administrator grants these, or someone with cluster-admin runs the install. Flux binds its helm-controller to cluster-admin"
  fi
}

pod_manifest() {
  local pod_namespace="$1" name="$2" label="$3" image="$4" user="$5" command="$6" hosts="$7"
  cat <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: ${name}
  namespace: ${pod_namespace}
  labels:
    app: ${label}
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: ${user}
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: check
      image: ${image}
      command: ["sh", "-c", "${command}"]
      env:
        - name: HOSTS
          value: "${hosts}"
      resources:
        requests:
          cpu: 10m
          memory: 16Mi
        limits:
          memory: 64Mi
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
EOF
}

run_client() {
  local name="$1" address="$2"
  pod_manifest "${test_namespace}" "${name}" preflight-client "${busybox_image}" 65534 "wget -q -T 5 -O - http://${address}:8080/ || echo polar-sky-blocked" "" |
    kubectl apply -f - >/dev/null 2>&1 || return 1
  kubectl wait pod "${name}" --namespace "${test_namespace}" --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s >/dev/null 2>&1 || return 1
  kubectl logs "${name}" --namespace "${test_namespace}" 2>/dev/null
}

check_network_policy() {
  local address baseline blocked
  if ! kubectl create namespace "${test_namespace}" >/dev/null 2>&1; then
    warn "could not create the test namespace ${test_namespace}" "NetworkPolicy enforcement is not tested; confirm with your platform team that the cluster enforces NetworkPolicy"
    return
  fi
  test_namespace_created=1
  pod_manifest "${test_namespace}" preflight-server preflight-server "${busybox_image}" 65534 "echo polar-sky-ok > /tmp/index.html && httpd -f -p 8080 -h /tmp" "" |
    kubectl apply -f - >/dev/null 2>&1
  if ! kubectl wait pod preflight-server --namespace "${test_namespace}" --for=condition=Ready --timeout=180s >/dev/null 2>&1; then
    warn "the NetworkPolicy test pod did not start (image ${busybox_image} from Docker Hub)" "check Docker Hub egress below; confirm with your platform team that the cluster enforces NetworkPolicy"
    return
  fi
  address="$(kubectl get pod preflight-server --namespace "${test_namespace}" -o jsonpath='{.status.podIP}' 2>/dev/null)"
  baseline="$(run_client preflight-client-before "${address}")"
  case "${baseline}" in
    *polar-sky-ok*) ;;
    *)
      warn "test pods in a new namespace cannot reach each other, even without a policy" "NetworkPolicy enforcement is not tested; confirm it with your platform team"
      return
      ;;
  esac
  kubectl apply -f - >/dev/null 2>&1 <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-server
  namespace: ${test_namespace}
spec:
  podSelector:
    matchLabels:
      app: preflight-server
  policyTypes: ["Ingress"]
EOF
  sleep 15
  blocked="$(run_client preflight-client-after "${address}")"
  case "${blocked}" in
    *polar-sky-ok*)
      fail "the cluster does not enforce NetworkPolicy" "turn on a NetworkPolicy engine: GKE Dataplane V2 or network policy enforcement; EKS VPC CNI network policy or Calico; AKS Azure, Calico or Cilium network policy"
      ;;
    *polar-sky-blocked*) pass "the cluster enforces NetworkPolicy" ;;
    *)
      fail "the NetworkPolicy test did not finish" "run preflight again; if it fails again, kubectl get pods -n ${test_namespace} shows why, and confirm with your platform team that the cluster enforces NetworkPolicy"
      ;;
  esac
}

check_egress() {
  local hosts host code connect_host results
  connect_host="${polar_sky_host%%:*}"
  hosts="${connect_host} us-docker.pkg.dev fluxcd-community.github.io ghcr.io registry-1.docker.io auth.docker.io oauth2.googleapis.com admin.googleapis.com www.googleapis.com ${model_host}"
  if ! kubectl get namespace "${namespace}" >/dev/null 2>&1; then
    fail "namespace ${namespace} does not exist, so egress is not tested" "create the namespace as cluster.md says, then run this again"
    return
  fi
  kubectl delete pod polar-sky-egress-check --namespace "${namespace}" --ignore-not-found --wait=true --timeout=60s >/dev/null 2>&1
  if ! pod_manifest "${namespace}" polar-sky-egress-check polar-sky-preflight "${curl_image}" 100 \
    'for h in $HOSTS; do c=0; curl -sS -o /dev/null --max-time 15 https://$h/ 2>/dev/null || c=$?; echo $h $c; done' "${hosts}" |
    kubectl apply -f - >/dev/null 2>&1; then
    fail "could not start the egress test pod in ${namespace}" "check that you may create pods there and that no admission policy blocks them"
    return
  fi
  if ! kubectl wait pod polar-sky-egress-check --namespace "${namespace}" --for=jsonpath='{.status.phase}'=Succeeded --timeout=300s >/dev/null 2>&1; then
    fail "the egress test pod did not finish (image ${curl_image} from Docker Hub)" "check that ${namespace} can pull from Docker Hub; kubectl describe pod polar-sky-egress-check -n ${namespace} shows why"
    return
  fi
  if ! results="$(kubectl logs polar-sky-egress-check --namespace "${namespace}" 2>/dev/null)" || [ -z "${results}" ]; then
    fail "could not read the egress test results" "you need permission to read pod logs in ${namespace} (kubectl logs); a cluster administrator grants it"
    return
  fi
  while read -r host code; do
    [ -n "${host}" ] || continue
    case "${code}" in
      0) pass "HTTPS to ${host}" ;;
      6) fail "DNS cannot resolve ${host} from ${namespace}" "allow DNS from the namespace and check the resolver" ;;
      7 | 28) fail "no HTTPS connection to ${host}:443 from ${namespace}" "the network team allows outbound TCP 443 from the namespace and from the CPU and GPU nodes to ${host}, including its redirect and download hosts" ;;
      60) fail "a proxy changes TLS to ${host}" "let ${host} pass without TLS inspection" ;;
      35 | 56)
        if [ "${host}" = "${connect_host}" ]; then
          pass "TLS to ${host} (it asks for the engine's certificate, as expected)"
        else
          warn "TLS to ${host} was cut off (curl code ${code})" "a proxy or firewall may be in the way; check with the network team"
        fi
        ;;
      *) warn "HTTPS to ${host} ended with curl code ${code}" "check with the network team" ;;
    esac
  done <<EOF
${results}
EOF
  warn "redirects to download hosts were not followed" "image and model pulls may be sent on to other download hosts; with a proxy or hostname allowlist, the whole chain must be allowed. Phase 6 shows any pull that still fails"
  warn "egress was tested from a CPU node only" "GPU nodes need the same outbound access; if they use another subnet or firewall, check it there too"
}

printf 'Polar Sky preflight, profile %s, namespace %s\n\n' "${profile}" "${namespace}"
check_cluster
check_nodes
check_gpu_nodes
check_storage_class
check_permissions
check_network_policy
check_egress
finish
