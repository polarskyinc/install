# Polar Sky install skill

The Polar Sky install skill lets your own AI agent install Polar Sky for your organization. It works with Claude Code, Codex, Cursor, GitHub Copilot, OpenCode and VS Code agents.

The skill runs on your machine with your own tools and accounts. It creates or checks your Kubernetes cluster, creates the Google service accounts, gets the engine certificate, installs the Polar Sky Document Processing Engine, and connects Google Workspace. It shows you every command first and asks before it changes anything.

## What you need

- macOS, Linux, or Windows with WSL
- An administrator account in your Polar Sky organization
- `kubectl`, Helm 3, OpenSSL and `gcloud`
- Terraform or OpenTofu 1.6 or later, for a new cluster
- `aws` for EKS, or `az` for AKS

## Install

Run these two commands in a terminal, then restart your agent:

```bash
npx add-mcp@<pinned version> https://mcp.polarsky.ai/admin -g
npx skills@<pinned version> add polarskyinc/install-skill -g
```

The first command connects your agent to the Polar Sky Admin server. The second adds the skill.

## Use

Ask your agent: "Install Polar Sky". The skill starts by signing you in to Polar Sky and reading your organization's install values.

The skill never prints or sends your private keys, service account keys or Kubernetes secrets. It sends Polar Sky only public things: the certificate signing request, service account emails, client IDs and the Workspace admin email.

## What is in this repository

| Path | What it is |
| --- | --- |
| `skills/polar-sky-install/SKILL.md` | The skill: rules and the order of the phases |
| `skills/polar-sky-install/references/` | One file for each phase |
| `skills/polar-sky-install/scripts/` | Helper scripts: detection, value check, preflight checks, certificate check |

## Changes

This repository is a published copy. Polar Sky makes changes in its main repository, where tests check the skill against the Polar Sky Admin server, and copies them here.

## License

Copyright Polar Sky Inc. All rights reserved. See [LICENSE](LICENSE).
