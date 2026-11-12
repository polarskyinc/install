#!/usr/bin/env bash
# Checks the install values exported from values.env and prints each one with every problem found; the values are public.
set -u

problems=0

problem() {
  printf 'PROBLEM  %s\n' "$1"
  problems=$((problems + 1))
}

show() {
  printf '%-30s %s\n' "$1" "${2:-<missing>}"
}

require() {
  local name="$1"
  local value="${!name:-}"
  show "${name}" "${value}"
  if [ -z "${value}" ]; then
    problem "${name} is missing from values.env"
    return 1
  fi
  case "${value}" in
    *[[:space:]]*) problem "${name} has a space in it" ;;
  esac
  return 0
}

check_scopes() {
  local name="$1"
  local value="${!name:-}"
  local scope
  local IFS=','
  for scope in ${value}; do
    case "${scope}" in
      https://www.googleapis.com/auth/?*) ;;
      *) problem "${name} has a scope that is not a Google scope URL: ${scope}" ;;
    esac
  done
}

deployment_model="${POLAR_SKY_DEPLOYMENT_MODEL:-}"
case "${deployment_model}" in
  cloud | on_prem)
    show POLAR_SKY_DEPLOYMENT_MODEL "${deployment_model}"
    ;;
  "")
    show POLAR_SKY_DEPLOYMENT_MODEL "on_prem (no line in values.env yet)"
    deployment_model=on_prem
    ;;
  hybrid)
    show POLAR_SKY_DEPLOYMENT_MODEL "on_prem (values.env has an older name for it)"
    deployment_model=on_prem
    ;;
  *)
    show POLAR_SKY_DEPLOYMENT_MODEL "${deployment_model}"
    problem "POLAR_SKY_DEPLOYMENT_MODEL must be cloud or on_prem"
    ;;
esac

provider="${POLAR_SKY_PROVIDER:-}"
case "${provider}" in
  google_workspace | microsoft365)
    show POLAR_SKY_PROVIDER "${provider}"
    ;;
  "")
    show POLAR_SKY_PROVIDER "google_workspace (no line in values.env yet)"
    provider=google_workspace
    ;;
  *)
    show POLAR_SKY_PROVIDER "${provider}"
    problem "POLAR_SKY_PROVIDER must be google_workspace or microsoft365"
    ;;
esac

if require POLAR_SKY_ORGANIZATION_ID; then
  printf '%s' "${POLAR_SKY_ORGANIZATION_ID}" | grep -Eq '^[A-Za-z0-9-]+$' ||
    problem "POLAR_SKY_ORGANIZATION_ID may hold only letters, digits and hyphens"
fi
show POLAR_SKY_ORGANIZATION_NAME "${POLAR_SKY_ORGANIZATION_NAME:-}"
[ -n "${POLAR_SKY_ORGANIZATION_NAME:-}" ] || problem "POLAR_SKY_ORGANIZATION_NAME is missing from values.env"

if [ "${deployment_model}" != cloud ]; then
  if [ -n "${POLAR_SKY_INFRA_PROFILE:-}" ]; then
    show POLAR_SKY_INFRA_PROFILE "${POLAR_SKY_INFRA_PROFILE}"
    case "${POLAR_SKY_INFRA_PROFILE}" in
      gke | eks | aks) ;;
      *) problem "POLAR_SKY_INFRA_PROFILE must be the setting value gke, eks or aks (for GKE, EKS or AKS)" ;;
    esac
  else
    show POLAR_SKY_INFRA_PROFILE "<not chosen yet: the plan sets it>"
  fi

  if require POLAR_SKY_CHART_VERSION; then
    printf '%s' "${POLAR_SKY_CHART_VERSION}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$' ||
      problem "POLAR_SKY_CHART_VERSION is not a version such as 0.3.4"
  fi

  if require POLAR_SKY_RELEASE_CHANNEL; then
    [ "${POLAR_SKY_RELEASE_CHANNEL}" = "latest" ] || problem "POLAR_SKY_RELEASE_CHANNEL must be latest"
  fi

  if require POLAR_SKY_CHART_REFERENCE; then
    printf '%s' "${POLAR_SKY_CHART_REFERENCE}" | grep -Eq '^oci://[a-z0-9.:/_-]+$' ||
      problem "POLAR_SKY_CHART_REFERENCE must look like oci://registry.example.com/charts/polar-sky-onprem"
  fi

  if require POLAR_SKY_HOST; then
    printf '%s' "${POLAR_SKY_HOST}" | grep -Eq '^[a-z0-9.-]+:[0-9]+$' ||
      problem "POLAR_SKY_HOST must look like connect.polarsky.ai:443"
  fi
fi

if [ -n "${POLAR_SKY_OKTA_PLANNED:-}" ]; then
  show POLAR_SKY_OKTA_PLANNED "${POLAR_SKY_OKTA_PLANNED}"
  case "${POLAR_SKY_OKTA_PLANNED}" in
    yes | no) ;;
    *) problem "POLAR_SKY_OKTA_PLANNED must be yes or no" ;;
  esac
fi

require POLAR_SKY_CONSOLE_URL || true

if [ "${provider}" != microsoft365 ] && require POLAR_SKY_CLOUD_SCOPES; then
  check_scopes POLAR_SKY_CLOUD_SCOPES
  if [ "${deployment_model}" = cloud ]; then
    for scope in drive drive.readonly; do
      case ",${POLAR_SKY_CLOUD_SCOPES}," in
        *",https://www.googleapis.com/auth/${scope},"*) ;;
        *) problem "POLAR_SKY_CLOUD_SCOPES must hold https://www.googleapis.com/auth/${scope} in a Cloud install, because Polar Sky Cloud reads file content" ;;
      esac
    done
  else
    case ",${POLAR_SKY_CLOUD_SCOPES}," in
      *,https://www.googleapis.com/auth/drive,* | *,https://www.googleapis.com/auth/drive.readonly,*)
        problem "POLAR_SKY_CLOUD_SCOPES must not hold drive or drive.readonly; the cloud account never reads file content"
        ;;
    esac
  fi
fi

if [ "${deployment_model}" != cloud ]; then
  if [ "${provider}" != microsoft365 ] && require POLAR_SKY_ON_PREM_SCOPES; then
    check_scopes POLAR_SKY_ON_PREM_SCOPES
  fi

  if require POLAR_SKY_NAMESPACE; then
    [ "${POLAR_SKY_NAMESPACE}" = "polar-sky-on-prem" ] || problem "POLAR_SKY_NAMESPACE must be polar-sky-on-prem"
  fi
fi

for name in GOOGLE_CLOUD_PROJECT_ID CLUSTER_PROJECT_ID; do
  value="${!name:-}"
  [ -n "${value}" ] || continue
  show "${name}" "${value}"
  printf '%s' "${value}" | grep -Eq '^[a-z][a-z0-9-]{4,28}[a-z0-9]$' ||
    problem "${name} is not a Google Cloud project ID"
done

if [ "${deployment_model}" != cloud ]; then
  if [ -n "${CLUSTER_SUBSCRIPTION_ID:-}" ]; then
    show CLUSTER_SUBSCRIPTION_ID "${CLUSTER_SUBSCRIPTION_ID}"
    printf '%s' "${CLUSTER_SUBSCRIPTION_ID}" | grep -Eq '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' ||
      problem "CLUSTER_SUBSCRIPTION_ID is not an Azure subscription ID"
  fi

  if [ -n "${CLUSTER_KUBERNETES_VERSION:-}" ]; then
    show CLUSTER_KUBERNETES_VERSION "${CLUSTER_KUBERNETES_VERSION}"
    printf '%s' "${CLUSTER_KUBERNETES_VERSION}" | grep -Eq '^1\.[0-9]+$' ||
      problem "CLUSTER_KUBERNETES_VERSION must be a minor version such as 1.35, without a patch number"
  fi

  if [ -n "${CLUSTER_SYSTEM_VM_SIZE:-}" ]; then
    show CLUSTER_SYSTEM_VM_SIZE "${CLUSTER_SYSTEM_VM_SIZE}"
    case "${CLUSTER_SYSTEM_VM_SIZE}" in
      Standard_D4s_v5 | Standard_D4ds_v5 | Standard_D4as_v5 | Standard_D4ads_v5 | Standard_D4s_v4 | Standard_D4ds_v4 | Standard_D4as_v4 | Standard_DC4ads_v5) ;;
      *) problem "CLUSTER_SYSTEM_VM_SIZE must be one of the system pool sizes the AKS recipe takes: Standard_D4s_v5, Standard_D4ds_v5, Standard_D4as_v5, Standard_D4ads_v5, Standard_D4s_v4, Standard_D4ds_v4, Standard_D4as_v4, Standard_DC4ads_v5" ;;
    esac
  fi

  if [ -n "${CLUSTER_GPU_ZONES:-}" ]; then
    show CLUSTER_GPU_ZONES "${CLUSTER_GPU_ZONES}"
    printf '%s' "${CLUSTER_GPU_ZONES}" | grep -Eq '^\["[a-z0-9-]+"(,"[a-z0-9-]+")*\]$' ||
      problem 'CLUSTER_GPU_ZONES must be a list of zones such as ["us-central1-a","us-central1-b"]'
  fi
fi

for name in GOOGLE_WORKSPACE_ADMIN_EMAIL GOOGLE_CLOUD_ACCOUNT; do
  value="${!name:-}"
  [ -n "${value}" ] || continue
  show "${name}" "${value}"
  printf '%s' "${value}" | grep -Eq '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' ||
    problem "${name} is not a plain email address"
done

for name in MICROSOFT_TENANT_ID MICROSOFT_CLOUD_APP_CLIENT_ID MICROSOFT_ON_PREM_APP_CLIENT_ID; do
  value="${!name:-}"
  [ -n "${value}" ] || continue
  show "${name}" "${value}"
  printf '%s' "${value}" | grep -Eq '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' ||
    problem "${name} is not an ID such as 00000000-0000-0000-0000-000000000000"
done

if [ -n "${MICROSOFT_CLOUD_APP_CERTIFICATE:-}" ]; then
  show MICROSOFT_CLOUD_APP_CERTIFICATE "${MICROSOFT_CLOUD_APP_CERTIFICATE}"
  printf '%s' "${MICROSOFT_CLOUD_APP_CERTIFICATE##*/}" | grep -Eq '^microsoft-cloud-app(-[0-9]{8})?\.crt$' ||
    problem "MICROSOFT_CLOUD_APP_CERTIFICATE must name microsoft-cloud-app.crt, or one with a date such as microsoft-cloud-app-20261109.crt"
fi

engine_certificate="${MICROSOFT_ON_PREM_APP_CERTIFICATE:-}"
engine_key_file="${MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE:-}"
if [ -n "${engine_certificate}" ] || [ -n "${engine_key_file}" ]; then
  show MICROSOFT_ON_PREM_APP_CERTIFICATE "${engine_certificate}"
  show MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE "${engine_key_file}"
  if [ -z "${engine_certificate}" ] || [ -z "${engine_key_file}" ]; then
    problem "MICROSOFT_ON_PREM_APP_CERTIFICATE and MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE go into values.env together, and one of them is missing"
  else
    printf '%s' "${engine_certificate##*/}" | grep -Eq '^microsoft-on-prem-app(-[0-9]{8})?\.crt$' ||
      problem "MICROSOFT_ON_PREM_APP_CERTIFICATE must name microsoft-on-prem-app.crt, or one with a date such as microsoft-on-prem-app-20261109.crt"
    [ "${engine_key_file}" = "${engine_certificate%.crt}.pem" ] ||
      problem "MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE must be the .pem with the same name and folder as MICROSOFT_ON_PREM_APP_CERTIFICATE, so the cluster gets the key of the certificate on the app"
  fi
fi

if [ -n "${MICROSOFT_SHAREPOINT_HOST:-}" ]; then
  show MICROSOFT_SHAREPOINT_HOST "${MICROSOFT_SHAREPOINT_HOST}"
  case "${MICROSOFT_SHAREPOINT_HOST}" in
    *-my.sharepoint.com)
      problem "MICROSOFT_SHAREPOINT_HOST must be the SharePoint host, such as contoso.sharepoint.com, not the OneDrive host that ends in -my.sharepoint.com"
      ;;
    *)
      printf '%s' "${MICROSOFT_SHAREPOINT_HOST}" | grep -Eq '^[a-z0-9][a-z0-9-]*\.sharepoint\.com$' ||
        problem "MICROSOFT_SHAREPOINT_HOST must be a host in lowercase such as contoso.sharepoint.com, with no https:// and no path"
      ;;
  esac
fi

if [ -n "${POLAR_SKY_ENGINE_CONNECTED_AT:-}" ]; then
  show POLAR_SKY_ENGINE_CONNECTED_AT "${POLAR_SKY_ENGINE_CONNECTED_AT}"
  printf '%s' "${POLAR_SKY_ENGINE_CONNECTED_AT}" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' ||
    problem "POLAR_SKY_ENGINE_CONNECTED_AT must be a UTC time such as 2026-11-09T14:05:00Z"
fi

if [ "${problems}" -eq 0 ]; then
  printf 'VALUES OK\n'
  exit 0
fi
printf 'VALUES HAVE %d PROBLEM(S)\n' "${problems}"
exit 1
