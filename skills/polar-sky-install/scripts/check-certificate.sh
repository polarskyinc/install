#!/usr/bin/env bash
# Checks client.crt in the current folder against client.key and the organization ID by comparing public-key hashes; never prints the key.
set -u

certificate="${1:-client.crt}"
key="${2:-client.key}"
problems=0

problem() {
  printf 'PROBLEM  %s\n' "$1"
  problems=$((problems + 1))
}

for file in "${certificate}" "${key}"; do
  [ -f "${file}" ] || problem "${file} is not in this folder"
done
if [ "${problems}" -gt 0 ]; then
  printf 'CERTIFICATE NOT OK\n'
  exit 1
fi

permissions="$(ls -l "${key}" | cut -c 2-10)"
case "${permissions}" in
  rw-------) ;;
  *) problem "${key} can be read by others (${permissions}); run: chmod 600 ${key}" ;;
esac

if ! openssl x509 -in "${certificate}" -noout -subject -issuer -dates; then
  problem "${certificate} is not a PEM certificate"
fi

common_name="$(openssl x509 -in "${certificate}" -noout -subject -nameopt multiline 2>/dev/null | sed -n 's/^ *commonName *= *//p')"
if [ -z "${POLAR_SKY_ORGANIZATION_ID:-}" ]; then
  problem "POLAR_SKY_ORGANIZATION_ID is not set; load values.env first"
elif [ "${common_name}" != "${POLAR_SKY_ORGANIZATION_ID}" ]; then
  problem "the certificate's CN is '${common_name}', not the organization ID ${POLAR_SKY_ORGANIZATION_ID}"
fi

if [ -f ca-chain.crt ]; then
  openssl verify -CAfile ca-chain.crt "${certificate}" >/dev/null 2>&1 ||
    problem "the certificate is not signed by the Polar Sky CA in ca-chain.crt"
else
  printf 'NOTE     ca-chain.crt is not in this folder, so the issuer is not checked\n'
fi

openssl x509 -in "${certificate}" -noout -checkend 0 >/dev/null || problem "the certificate has expired"

certificate_public_key="$(openssl x509 -in "${certificate}" -noout -pubkey 2>/dev/null)"
key_public_key="$(openssl pkey -in "${key}" -pubout 2>/dev/null)"
[ -n "${certificate_public_key}" ] || problem "could not read the public key in ${certificate}"
[ -n "${key_public_key}" ] || problem "could not read ${key} as a private key"
certificate_hash="$(printf '%s\n' "${certificate_public_key}" | openssl sha256 | awk '{print $NF}')"
key_hash="$(printf '%s\n' "${key_public_key}" | openssl sha256 | awk '{print $NF}')"
printf 'certificate public key sha256  %s\n' "${certificate_hash}"
printf 'key public key sha256          %s\n' "${key_hash}"
if [ -z "${certificate_public_key}" ] || [ -z "${key_public_key}" ] || [ "${certificate_hash}" != "${key_hash}" ]; then
  problem "the certificate was not made for this key; make a new key and request on this machine"
fi

if [ "${problems}" -eq 0 ]; then
  printf 'CERTIFICATE OK\n'
  exit 0
fi
printf 'CERTIFICATE NOT OK\n'
exit 1
