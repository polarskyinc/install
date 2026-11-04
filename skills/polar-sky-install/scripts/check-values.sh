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

if [ -n "${POLAR_SKY_DEPLOYMENT_MODEL:-}" ]; then
  show POLAR_SKY_DEPLOYMENT_MODEL "${POLAR_SKY_DEPLOYMENT_MODEL}"
else
  show POLAR_SKY_DEPLOYMENT_MODEL "hybrid (no line in values.env)"
fi
deployment_model="${POLAR_SKY_DEPLOYMENT_MODEL:-hybrid}"
case "${deployment_model}" in
  cloud | hybrid) ;;
  *) problem "POLAR_SKY_DEPLOYMENT_MODEL must be cloud or hybrid" ;;
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

  if require POLAR_SKY_HOST; then
    printf '%s' "${POLAR_SKY_HOST}" | grep -Eq '^[a-z0-9.-]+:[0-9]+$' ||
      problem "POLAR_SKY_HOST must look like connect.polarsky.ai:443"
  fi
fi

require POLAR_SKY_CONSOLE_URL || true

if require POLAR_SKY_CLOUD_SCOPES; then
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
  if require POLAR_SKY_ON_PREM_SCOPES; then check_scopes POLAR_SKY_ON_PREM_SCOPES; fi

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

if [ "${problems}" -eq 0 ]; then
  printf 'VALUES OK\n'
  exit 0
fi
printf 'VALUES HAVE %d PROBLEM(S)\n' "${problems}"
exit 1
