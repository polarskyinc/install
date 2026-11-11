#!/usr/bin/env bash
# Checks the permissions admin consent granted a Polar Sky app registration against microsoft-permissions.json in the current folder and, when a certificate file is given, that the certificate is on the app; reads only and prints no secret.
set -u

usage() {
  printf 'usage: check-microsoft-app.sh <cloud|engine> <client id> [certificate file]\n' >&2
  exit 2
}

case "${1:-}" in
  cloud) holder=polar_sky_cloud ;;
  engine) holder=engine ;;
  *) usage ;;
esac
client_id="${2:-}"
certificate="${3:-}"
[ -n "${client_id}" ] || usage

problems=0

problem() {
  printf 'PROBLEM  %s\n' "$1"
  problems=$((problems + 1))
}

entry() {
  printf '%-8s %-29s %s\n' "$1" "$2" "$3"
}

not_ok() {
  printf 'APP NOT OK\n'
  exit 1
}

for tool in az jq openssl; do
  command -v "${tool}" >/dev/null 2>&1 || problem "${tool} is not installed"
done
case "${POLAR_SKY_DEPLOYMENT_MODEL:-}" in
  cloud) model=cloud ;;
  on_prem | hybrid) model=on_prem ;;
  *) problem "POLAR_SKY_DEPLOYMENT_MODEL is not set to cloud or on_prem; load values.env first" ;;
esac
[ -f microsoft-permissions.json ] || problem "microsoft-permissions.json is not in this folder"
[ "${problems}" -eq 0 ] || not_ok

if ! expected="$(jq -ce --arg holder "${holder}" '[.[] | select(.required_for == $holder) | {api, api_app_id, permission, required}]' microsoft-permissions.json 2>/dev/null)"; then
  problem "microsoft-permissions.json does not hold the permission list from Polar Sky"
  not_ok
fi
if [ "$(jq 'length' <<<"${expected}")" -eq 0 ]; then
  problem "microsoft-permissions.json lists no permission for this app"
  not_ok
fi

if ! principal_id="$(az ad sp show --id "${client_id}" --query id -o tsv 2>/dev/null | tr -d '\r')" || [ -z "${principal_id}" ]; then
  problem "the app ${client_id} has no service principal in this tenant, or this sign-in cannot read it"
  not_ok
fi
printf '%-39s%s\n' "service principal" "${principal_id}"

assignments='[]'
page_url="https://graph.microsoft.com/v1.0/servicePrincipals/${principal_id}/appRoleAssignments"
while [ -n "${page_url}" ]; do
  if ! page="$(az rest --method GET --url "${page_url}" -o json 2>/dev/null)" ||
    ! assignments="$(jq -ce --argjson page "${page}" '. + [($page.value // [])[] | {id, role: .appRoleId, resource: .resourceId}]' <<<"${assignments}" 2>/dev/null)"; then
    problem "could not read the permissions granted to the app"
    not_ok
  fi
  page_url="$(jq -r '."@odata.nextLink" // empty' <<<"${page}")"
done

granted='[]'
for resource_id in $(jq -r '[.[].resource] | unique | .[]' <<<"${assignments}"); do
  if ! resource="$(az ad sp show --id "${resource_id}" --query '{appId: appId, name: displayName, roles: appRoles[].{id: id, value: value}}' -o json 2>/dev/null)"; then
    problem "could not read the API ${resource_id} that a grant points to"
    continue
  fi
  granted="$(jq -c --arg resource "${resource_id}" --argjson described "${resource}" --argjson assignments "${assignments}" '
    . + [$assignments[] | select(.resource == $resource) | .role as $role
      | {api_app_id: $described.appId, api: $described.name, id,
         permission: ([($described.roles // [])[] | select(.id == $role) | .value] | .[0] // $role)}]
  ' <<<"${granted}")"
done

features_waiting=0
while IFS=$'\t' read -r api api_app_id permission required; do
  [ -n "${api_app_id}" ] || continue
  if jq -e --arg api "${api_app_id}" --arg permission "${permission}" 'any(.[]; .api_app_id == $api and .permission == $permission)' <<<"${granted}" >/dev/null; then
    entry "granted" "${api}" "${permission}"
  elif [ "${required}" = false ]; then
    entry "MISSING" "${api}" "${permission} (Polar Sky connects without it; the feature it serves waits)"
    features_waiting=$((features_waiting + 1))
  else
    entry "MISSING" "${api}" "${permission}"
    problems=$((problems + 1))
  fi
done < <(jq -r '.[] | [.api, .api_app_id, .permission, (.required != false | tostring)] | @tsv' <<<"${expected}")

while IFS=$'\t' read -r api permission assignment_id; do
  [ -n "${assignment_id}" ] || continue
  if [ "${holder}" = polar_sky_cloud ] && [ "${model}" = on_prem ]; then
    entry "SURPLUS" "${api}" "${permission} (grant ${assignment_id})"
    problem "${api} ${permission} is granted, but Polar Sky Cloud must not hold it in an On-Prem install"
  else
    entry "EXTRA" "${api}" "${permission} (granted, but Polar Sky does not ask for it; grant ${assignment_id})"
  fi
done < <(jq -r --argjson expected "${expected}" '
  .[] | select(.api_app_id as $api | .permission as $permission
    | $expected | any(.api_app_id == $api and .permission == $permission) | not)
  | [.api, .permission, .id] | @tsv
' <<<"${granted}")

if [ -n "${certificate}" ]; then
  thumbprint="$(openssl x509 -in "${certificate}" -noout -fingerprint -sha1 2>/dev/null | cut -d= -f2 | tr -d ':' | tr '[:lower:]' '[:upper:]')"
  if [ -z "${thumbprint}" ]; then
    problem "${certificate} is not a PEM certificate"
  else
    openssl x509 -in "${certificate}" -noout -checkend 0 >/dev/null || problem "the certificate in ${certificate} has expired"
    thumbprint_base64="$(printf '%b' "$(printf '%s' "${thumbprint}" | sed 's/../\\x&/g')" | openssl base64 -A)"
    if ! identifiers="$(az ad app credential list --id "${client_id}" --cert --query '[].customKeyIdentifier' -o tsv 2>/dev/null)"; then
      problem "could not read the certificates on the app"
    else
      on_app=no
      while IFS= read -r identifier; do
        identifier="${identifier%$'\r'}"
        [ -n "${identifier}" ] || continue
        if [ "${identifier}" = "${thumbprint_base64}" ] ||
          [ "$(printf '%s' "${identifier}" | tr -d ':' | tr '[:lower:]' '[:upper:]')" = "${thumbprint}" ]; then
          on_app=yes
        fi
      done <<<"${identifiers}"
      if [ "${on_app}" = yes ]; then
        printf '%-39s%s\n' "certificate on the app" "${thumbprint}"
      else
        problem "the certificate in ${certificate} is not on the app; add it to the app again"
      fi
    fi
  fi
else
  printf 'certificate: not checked (no certificate from this install)\n'
fi

if [ "${problems}" -eq 0 ] && [ "${features_waiting}" -gt 0 ]; then
  printf 'APP INCOMPLETE\n'
  exit 1
fi
if [ "${problems}" -eq 0 ]; then
  printf 'APP OK\n'
  exit 0
fi
not_ok
