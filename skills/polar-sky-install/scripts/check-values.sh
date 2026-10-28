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

if require POLAR_SKY_ORGANIZATION_ID; then
  printf '%s' "${POLAR_SKY_ORGANIZATION_ID}" | grep -Eq '^[A-Za-z0-9-]+$' ||
    problem "POLAR_SKY_ORGANIZATION_ID may hold only letters, digits and hyphens"
fi
show POLAR_SKY_ORGANIZATION_NAME "${POLAR_SKY_ORGANIZATION_NAME:-}"
[ -n "${POLAR_SKY_ORGANIZATION_NAME:-}" ] || problem "POLAR_SKY_ORGANIZATION_NAME is missing from values.env"

if [ -n "${POLAR_SKY_INFRA_PROFILE:-}" ]; then
  show POLAR_SKY_INFRA_PROFILE "${POLAR_SKY_INFRA_PROFILE}"
  case "${POLAR_SKY_INFRA_PROFILE}" in
    gke | eks | aks) ;;
    *) problem "POLAR_SKY_INFRA_PROFILE must be gke, eks or aks" ;;
  esac
else
  show POLAR_SKY_INFRA_PROFILE "<not chosen yet: phase 2 sets it>"
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
require POLAR_SKY_CONSOLE_URL || true

if require POLAR_SKY_CLOUD_SCOPES; then
  check_scopes POLAR_SKY_CLOUD_SCOPES
  case ",${POLAR_SKY_CLOUD_SCOPES}," in
    *,https://www.googleapis.com/auth/drive,* | *,https://www.googleapis.com/auth/drive.readonly,*)
      problem "POLAR_SKY_CLOUD_SCOPES must not hold drive or drive.readonly; the cloud account never reads file content"
      ;;
  esac
fi
if require POLAR_SKY_ON_PREM_SCOPES; then check_scopes POLAR_SKY_ON_PREM_SCOPES; fi

if require POLAR_SKY_NAMESPACE; then
  [ "${POLAR_SKY_NAMESPACE}" = "polar-sky-on-prem" ] || problem "POLAR_SKY_NAMESPACE must be polar-sky-on-prem"
fi

for name in GOOGLE_CLOUD_PROJECT_ID CLUSTER_PROJECT_ID; do
  value="${!name:-}"
  [ -n "${value}" ] || continue
  show "${name}" "${value}"
  printf '%s' "${value}" | grep -Eq '^[a-z][a-z0-9-]{4,28}[a-z0-9]$' ||
    problem "${name} is not a Google Cloud project ID"
done

if [ -n "${GOOGLE_WORKSPACE_ADMIN_EMAIL:-}" ]; then
  show GOOGLE_WORKSPACE_ADMIN_EMAIL "${GOOGLE_WORKSPACE_ADMIN_EMAIL}"
  printf '%s' "${GOOGLE_WORKSPACE_ADMIN_EMAIL}" | grep -Eq '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' ||
    problem "GOOGLE_WORKSPACE_ADMIN_EMAIL is not a plain email address"
fi

if [ "${problems}" -eq 0 ]; then
  printf 'VALUES OK\n'
  exit 0
fi
printf 'VALUES HAVE %d PROBLEM(S)\n' "${problems}"
exit 1
