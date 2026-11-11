#!/usr/bin/env bash
# Prints the tools, cloud accounts and Kubernetes context on this machine; reads only, and tests sign-ins by exit status so no token is printed. With cloud, it prints only what a Cloud install needs (gcloud for Google Workspace; az, jq and openssl for microsoft365); with no argument, what an On-Prem install needs.
set -u

model="${1:-on_prem}"
provider="${2:-google_workspace}"
case "${model}:${provider}" in
  cloud:google_workspace | cloud:microsoft365 | on_prem:google_workspace | on_prem:microsoft365) ;;
  *)
    printf 'usage: detect.sh [cloud|on_prem] [google_workspace|microsoft365]\n' >&2
    exit 2
    ;;
esac

line() { printf '%-22s %s\n' "$1" "$2"; }

first_line() { head -n 1 | tr -d '\r'; }

have() { command -v "$1" >/dev/null 2>&1; }

azure_sign_in() {
  if ! have az; then
    line "az" "not found"
    return
  fi
  local signed_in tenant
  if [ "${model}" = on_prem ]; then
    signed_in="$(az account show --query '[name, user.name]' -o tsv 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')"
    line "az subscription" "${signed_in:-not signed in}"
  else
    signed_in="$(az account show --query user.name -o tsv 2>/dev/null | first_line)"
    line "az account" "${signed_in:-not signed in}"
  fi
  if [ -z "${signed_in}" ]; then
    return
  fi
  tenant="$(az account show --query tenantId -o tsv 2>/dev/null | first_line)"
  line "az tenant" "${tenant:-unknown}"
  if az account get-access-token </dev/null >/dev/null 2>&1; then
    line "az sign-in" "works"
  else
    line "az sign-in" "expired or refused"
  fi
}

line "platform" "$(uname -s 2>/dev/null || echo unknown)"

if [ "${model}" = cloud ] && [ "${provider}" = microsoft365 ]; then
  azure_sign_in
  if have jq; then line "jq" "found"; else line "jq" "not found"; fi
  if have openssl; then
    line "openssl" "$(openssl version 2>/dev/null | first_line)"
  else
    line "openssl" "not found"
  fi
  exit 0
fi

if have gcloud; then
  account="$(gcloud config get-value account 2>/dev/null | first_line)"
  project="$(gcloud config get-value project 2>/dev/null | first_line)"
  line "gcloud account" "${account:-not signed in}"
  line "gcloud project" "${project:-none set}"
  if [ -n "${account}" ]; then
    if gcloud auth print-access-token </dev/null >/dev/null 2>&1; then
      line "gcloud sign-in" "works"
    else
      line "gcloud sign-in" "expired or refused"
    fi
  fi
  if [ "${model}" = on_prem ]; then
    if gcloud auth application-default print-access-token >/dev/null 2>&1; then
      line "gcloud ADC" "works"
    else
      line "gcloud ADC" "not signed in, or the sign-in has expired"
    fi
  fi
else
  line "gcloud" "not found"
fi

if [ "${model}" = cloud ]; then
  exit 0
fi

if have aws; then
  identity="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null | first_line)"
  line "aws identity" "${identity:-not signed in}"
else
  line "aws" "not found"
fi

azure_sign_in

if have kubelogin; then line "kubelogin" "found"; else line "kubelogin" "not found"; fi

if have jq; then line "jq" "found"; else line "jq" "not found"; fi

if have terraform; then
  line "terraform" "$(terraform version 2>/dev/null | first_line)"
else
  line "terraform" "not found"
fi

if have tofu; then
  line "tofu" "$(tofu version 2>/dev/null | first_line)"
else
  line "tofu" "not found"
fi

if have kubectl; then
  context="$(kubectl config current-context 2>/dev/null | first_line)"
  line "kubectl context" "${context:-none}"
  if [ -n "${context}" ]; then
    if kubectl version --request-timeout=10s >/dev/null 2>&1; then
      line "kubectl reaches" "yes"
    else
      line "kubectl reaches" "no (not signed in, or the cluster does not answer)"
    fi
  fi
else
  line "kubectl" "not found"
fi

if have helm; then
  line "helm" "$(helm version --short 2>/dev/null | first_line)"
else
  line "helm" "not found"
fi

if have openssl; then
  line "openssl" "$(openssl version 2>/dev/null | first_line)"
else
  line "openssl" "not found"
fi
