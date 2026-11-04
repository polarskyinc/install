#!/usr/bin/env bash
# Prints the tools, cloud accounts and Kubernetes context on this machine; reads only, and tests sign-ins by exit status so no token is printed. With cloud, it prints only what a Cloud install needs.
set -u

model="${1:-hybrid}"
case "${model}" in
  cloud | hybrid) ;;
  *)
    printf 'usage: detect.sh [cloud|hybrid]\n' >&2
    exit 2
    ;;
esac

line() { printf '%-22s %s\n' "$1" "$2"; }

first_line() { head -n 1 | tr -d '\r'; }

have() { command -v "$1" >/dev/null 2>&1; }

line "platform" "$(uname -s 2>/dev/null || echo unknown)"

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
  if [ "${model}" = hybrid ]; then
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

if have az; then
  subscription="$(az account show --query '[name, user.name]' -o tsv 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')"
  line "az subscription" "${subscription:-not signed in}"
  if [ -n "${subscription}" ]; then
    if az account get-access-token </dev/null >/dev/null 2>&1; then
      line "az sign-in" "works"
    else
      line "az sign-in" "expired or refused"
    fi
  fi
else
  line "az" "not found"
fi

if have kubelogin; then line "kubelogin" "found"; else line "kubelogin" "not found"; fi

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
