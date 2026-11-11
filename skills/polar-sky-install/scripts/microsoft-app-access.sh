#!/usr/bin/env bash
# Builds the permission list for a Polar Sky app registration from microsoft-permissions.json in the current folder, keeping the app's other entries, and prints what changes and what admin consent would grant; it writes only that one public file, changes nothing in Microsoft Entra ID and prints no secret.
set -u

readonly microsoft_graph='00000003-0000-0000-c000-000000000000'
readonly sharepoint_online='00000003-0000-0ff1-ce00-000000000000'
readonly office_365_management='c5393580-f805-4401-95e8-94b7a6ef2fc2'

usage() {
  printf 'usage: microsoft-app-access.sh <cloud|engine> <client id> [certificate file]\n' >&2
  exit 2
}

case "${1:-}" in
  cloud)
    holder=polar_sky_cloud
    output=microsoft-cloud-app-access.json
    ;;
  engine)
    holder=engine
    output=microsoft-on-prem-app-access.json
    ;;
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

not_written() {
  printf 'ACCESS FILE NOT WRITTEN\n'
  exit 1
}

for tool in az jq openssl; do
  command -v "${tool}" >/dev/null 2>&1 || problem "${tool} is not installed"
done
printf '%s' "${client_id}" | grep -Eq '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' ||
  problem "the client ID is not an ID such as 00000000-0000-0000-0000-000000000000"
[ -f microsoft-permissions.json ] || problem "microsoft-permissions.json is not in this folder"
[ "${problems}" -eq 0 ] || not_written

if ! wanted="$(jq -ce --arg holder "${holder}" '[.[] | select(.required_for == $holder) | {api, api_app_id, permission}]' microsoft-permissions.json 2>/dev/null)"; then
  problem "microsoft-permissions.json does not hold the permission list from Polar Sky"
  not_written
fi
if [ "$(jq 'length' <<<"${wanted}")" -eq 0 ]; then
  problem "microsoft-permissions.json lists no permission for this app"
  not_written
fi

if [ -n "${certificate}" ]; then
  if end="$(openssl x509 -in "${certificate}" -noout -enddate 2>/dev/null)"; then
    end_date="$(printf '%s\n' "${end#notAfter=}" | awk '{
      split("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec", names, " ")
      for (number = 1; number <= 12; number++) if (names[number] == $1) month = number
      printf "%s-%02d-%02dT%sZ\n", $4, month, $2, $3
    }')"
    printf '%-39s%s\n' "certificate end date" "${end_date}"
  else
    problem "${certificate} is not a PEM certificate"
  fi
fi

catalogue='{}'

describe_api() {
  local api_app_id="$1" described
  if jq -e --arg id "${api_app_id}" 'has($id)' <<<"${catalogue}" >/dev/null; then
    return 0
  fi
  if ! described="$(az ad sp show --id "${api_app_id}" --query '{name: displayName, roles: appRoles[].{id: id, value: value, members: allowedMemberTypes}, scopes: oauth2PermissionScopes[].{id: id, value: value}}' -o json 2>/dev/null)"; then
    return 1
  fi
  catalogue="$(jq -c --arg id "${api_app_id}" --argjson described "${described}" '. + {($id): $described}' <<<"${catalogue}")"
}

declared='[]'
for api_app_id in $(jq -r '[.[].api_app_id] | unique | .[]' <<<"${wanted}"); do
  api_name="$(jq -r --arg id "${api_app_id}" 'map(select(.api_app_id == $id)) | .[0].api' <<<"${wanted}")"
  if ! describe_api "${api_app_id}"; then
    problem "could not read the permissions ${api_name} offers; sign in to the tenant with an account that may read the directory"
    continue
  fi
  roles="$(jq -c --arg id "${api_app_id}" '.[$id].roles // [] | map(select((.members // ["Application"]) | index("Application")))' <<<"${catalogue}")"
  while IFS= read -r permission; do
    [ -n "${permission}" ] || continue
    problem "${api_name} has no application permission named ${permission}"
  done < <(jq -r --arg id "${api_app_id}" --argjson roles "${roles}" '.[] | select(.api_app_id == $id) | .permission | select(. as $name | $roles | any(.value == $name) | not)' <<<"${wanted}")
  declared="$(jq -c --arg id "${api_app_id}" --argjson roles "${roles}" --argjson wanted "${wanted}" '. + [{resourceAppId: $id, resourceAccess: [$wanted[] | select(.api_app_id == $id) | .permission as $name | $roles[] | select(.value == $name) | {id, type: "Role"}]}]' <<<"${declared}")"
done
[ "${problems}" -eq 0 ] || not_written

if ! existing="$(az ad app show --id "${client_id}" --query requiredResourceAccess -o json 2>/dev/null)"; then
  problem "could not read the app registration ${client_id}"
  not_written
fi
if [ -z "${existing}" ] || [ "${existing}" = null ]; then
  existing='[]'
fi

owned="$(jq -c --arg graph "${microsoft_graph}" --arg sharepoint "${sharepoint_online}" --arg management "${office_365_management}" '[$graph, $sharepoint, $management] + map(.resourceAppId) | unique' <<<"${declared}")"

for api_app_id in $(jq -r '.[].resourceAppId' <<<"${existing}"); do
  describe_api "${api_app_id}" || true
done

merged="$(jq -c --argjson declared "${declared}" --argjson owned "${owned}" '
  . as $existing
  | map(select(.resourceAppId as $api | $owned | index($api) | not)) as $others
  | $others + ($owned | map(
      . as $api
      | [$existing[] | select(.resourceAppId == $api) | .resourceAccess[] | select(.type != "Role")] as $scopes
      | [$declared[] | select(.resourceAppId == $api) | .resourceAccess[]] as $roles
      | {resourceAppId: $api, resourceAccess: ($scopes + $roles)}
    ) | map(select(.resourceAccess | length > 0)))
' <<<"${existing}")"

name_of() {
  jq -r --arg api "$1" --arg id "$2" --arg type "$3" '
    (.[$api] // {}) as $described
    | (if $type == "Role" then $described.roles else $described.scopes end // [])
    | map(select(.id == $id)) | if length > 0 then .[0].value else $id end
  ' <<<"${catalogue}"
}

api_label() {
  jq -r --arg api "$1" '.[$api].name // $api' <<<"${catalogue}"
}

while IFS=$'\t' read -r api_name permission; do
  [ -n "${api_name}" ] || continue
  entry "request" "${api_name}" "${permission}"
done < <(jq -r '.[] | [.api, .permission] | @tsv' <<<"${wanted}")

while IFS=$'\t' read -r api_app_id role_id; do
  [ -n "${api_app_id}" ] || continue
  entry "REMOVE" "$(api_label "${api_app_id}")" "$(name_of "${api_app_id}" "${role_id}" Role) (an application permission Polar Sky does not ask for)"
done < <(jq -r --argjson declared "${declared}" --argjson owned "${owned}" '
  .[] | select(.resourceAppId as $api | $owned | index($api))
  | .resourceAppId as $api
  | .resourceAccess[] | select(.type == "Role")
  | select(.id as $id | [$declared[] | select(.resourceAppId == $api) | .resourceAccess[].id] | index($id) | not)
  | [$api, .id] | @tsv
' <<<"${existing}")

while IFS=$'\t' read -r api_app_id access_id access_type; do
  [ -n "${api_app_id}" ] || continue
  kind=application
  [ "${access_type}" = Role ] || kind=delegated
  entry "KEEP" "$(api_label "${api_app_id}")" "$(name_of "${api_app_id}" "${access_id}" "${access_type}") (${kind}; admin consent grants it too)"
done < <(jq -r --argjson owned "${owned}" '
  .[] | .resourceAppId as $api
  | .resourceAccess[]
  | select(($owned | index($api) | not) or .type != "Role")
  | [$api, .id, .type] | @tsv
' <<<"${existing}")

if ! jq . <<<"${merged}" >"${output}"; then
  problem "could not write ${output}"
  not_written
fi
printf 'ACCESS FILE WRITTEN  %s\n' "${output}"
