# Polar Sky install skill

This skill lets your own AI agent install Polar Sky for your organization. It works with Claude Code and Codex.

## For AI agents

If a person asked you to install Polar Sky from this repository, start a conversation, not a script. First tell them, in a few short sentences, what will happen: you will connect to the Polar Sky Install server, add the install skill, and then they may need to restart you so the server loads. Then do these three steps.

1. **Add the Polar Sky Install MCP server.** Its address is `https://mcp.polarsky.ai/install`. It uses streamable HTTP and OAuth sign-in. In Claude Code, run:

   ```bash
   claude mcp add --scope user --transport http polar-sky-install https://mcp.polarsky.ai/install
   ```

   In Codex, run:

   ```bash
   codex mcp add polar-sky-install --url https://mcp.polarsky.ai/install
   ```

   Polar Sky supports Claude Code and Codex. In another agent, tell the person that Polar Sky does not support it yet, and stop.
2. **Get the skill.** If you can install skills, run `npx skills@1.7.4 add polarskyinc/install -g --skill polar-sky-install`. If you cannot, read [`skills/polar-sky-install/SKILL.md`](skills/polar-sky-install/SKILL.md) in this repository and follow it, with the files it links to.
3. **Start.** In Claude Code, the person first types `/mcp`: if `polar-sky-install` is listed, they choose it and **Authenticate**, and the tools load without a restart. Otherwise, or in Codex, tell the person that they need to restart you before the MCP server loads, and how. Then start phase 1 of the skill.

The skill's hard rules apply from the first command. Read them in the "Hard rules" section of `SKILL.md` before you run anything.

## What Polar Sky installs

Polar Sky finds files that too many people can open, and proposes controls your team approves. It works with Google Workspace or Microsoft 365. You choose one of two deployments when the install starts:

- **Cloud.** Polar Sky Cloud reads your files' content, and nothing runs in your cloud. For Google Workspace, this install sets up one Google service account in your Google Cloud project, its delegation entry, and the connection to Google Workspace. For Microsoft 365, it sets up one app registration in your Microsoft Entra ID, with a certificate made on your machine, and the connection to Microsoft 365. There is no cluster to build.
- **On-Prem.** An engine in your own cloud reads your files' content, so Polar Sky Cloud never sees it. This install sets up a Kubernetes cluster with GPU nodes (on GKE, EKS or AKS), the engine certificate and the engine. For Google Workspace, it also sets up two Google service accounts (one for the engine and one for Polar Sky Cloud) and the connection to Google Workspace. For Microsoft 365, it sets up two app registrations (`Polar Sky On-Premises` for the engine, whose key goes only into your cluster, and `Polar Sky Cloud`, which reads no file content) and the connection to Microsoft 365. The agent can build a new cluster from Polar Sky's recipe, or use one you have.

In both, a Google Workspace super admin approves what each service account may do, and no one's password is used. At the end, you choose which drives Polar Sky monitors, in the conversation or in the Polar Sky console.

With Microsoft 365, a Global Administrator or Privileged Role Administrator grants admin consent to the app registrations, and no one's password is used. Polar Sky monitors every SharePoint site and everyone's OneDrive.

If your organization already has an engine, its install is On-Prem, and the agent says so.

## What you need

For a Cloud install with Google Workspace:

- macOS, Linux, or Windows with WSL
- An administrator account in your Polar Sky organization
- `gcloud`, signed in to a Google Cloud project you can use
- A Google Workspace super admin, for a few minutes, to add the delegation entry

For a Cloud install with Microsoft 365:

- macOS, Linux, or Windows with WSL
- An administrator account in your Polar Sky organization
- `az` (the Azure CLI), `jq` and OpenSSL; `az` signs in to your Microsoft 365 tenant, with or without an Azure subscription
- The right to register applications in Microsoft Entra ID, which every user has by default
- A Global Administrator or Privileged Role Administrator, for a few minutes, to grant admin consent
- Audit logging turned on in Microsoft Purview

For an On-Prem install, in addition to the Cloud list above for your provider (and with Microsoft 365 on GKE, `gcloud` too):

- `kubectl`, Helm 3 or 4, and OpenSSL
- Terraform or OpenTofu 1.6 or later, for a new cluster
- `aws` for EKS, or `az` for AKS

## What will happen, and how long it takes

A Cloud install is much shorter. It has no cluster to build and no AI models to load, so most of its time is the super admin's approval.

An On-Prem install usually takes one to two hours, most of it waiting for the cluster and the AI models.

1. The agent signs you in to Polar Sky and looks at your machine and your cloud. It only reads.
2. It asks which deployment you want, then asks any open questions in one message.
3. It shows you one final plan: what it found, what it will create, and how long each step takes. You check it and say yes, or change it.
4. It works step by step. Before each step it shows you that step's plan, such as the cluster plan in an On-Prem install, and asks once. It shows every command it runs. It asks again before it deletes or replaces anything, before a cost the plan did not cover, before it grants admin consent, and before it uploads the cloud service account key or the Microsoft 365 certificate bundle.
5. In an On-Prem install, slow steps run side by side: while the cluster builds, the agent creates the Google service accounts and prepares the request for your super admin, or with Microsoft 365 creates the app registrations and the consent request for your administrator.

Optionally, after the install is done and only when you ask for it, the agent can put the accounts of Polar Sky's AI helpers in a Google Cloud project you own (Google Workspace only). You then own and control those accounts. Google Drive still treats them as outside your Workspace, so a Shared Drive that blocks outside sharing has to allow it before a helper can read there. It needs someone who can change an organization policy, and the agent says which steps need which rights.

## Install

Run two commands in a terminal. If your agent was already running and `/mcp` does not list the server, restart it. Restart Codex in any case.

First, connect your agent to the Polar Sky Install server. In Claude Code:

```bash
claude mcp add --scope user --transport http polar-sky-install https://mcp.polarsky.ai/install
```

In Codex:

```bash
codex mcp add polar-sky-install --url https://mcp.polarsky.ai/install
```

Then add the skill:

```bash
npx skills@1.7.4 add polarskyinc/install -g --skill polar-sky-install
```

Then sign in to Polar Sky: in Claude Code, type `/mcp`, choose `polar-sky-install` and **Authenticate**; in Codex, run `codex mcp login polar-sky-install`. Both open Polar Sky's sign-in page in your browser.

## Use

Ask your agent: "Install Polar Sky". The skill starts by signing you in to Polar Sky, reading your organization's install values and looking at your machine. Then it asks whether you use Google Workspace or Microsoft 365, and whether you want a Cloud or an On-Prem deployment.

The skill never prints your private keys, service account keys or Kubernetes secrets, and never puts them in the chat. It sends Polar Sky public things: the certificate signing request, service account emails, client IDs, the Microsoft 365 tenant ID and the Workspace admin email. The one secret Polar Sky receives is the cloud service account key for Google Workspace, or the cloud app's certificate bundle for Microsoft 365, which the skill uploads once with `curl`, straight from the file, with a one-time upload token; Polar Sky stores it encrypted, and the skill then deletes the file.

## Polar Sky skills in Claude Code

At the end of the install, in Claude Code, the agent adds Polar Sky's skills with the `polar-sky-access-reviews` plugin. With it, you can ask Claude for an access review report for your auditor, or for the audit trail of what changed in a date range. To add it yourself, run:

```bash
claude plugin marketplace add polarskyinc/install
claude plugin install polar-sky-access-reviews@polar-sky --scope user
```

## Polar Sky status in Claude Code

Once Polar Sky is installed, you can add a band above the Claude Code prompt that shows your folder and control status whenever Claude uses a Polar Sky connector. In Claude Code, run:

```
/plugin install polar-sky-status --marketplace polarskyinc/install
```

See [`plugins/polar-sky-status/README.md`](plugins/polar-sky-status/README.md) for what it shows and the permission it needs in auto mode.

## What is in this repository

| Path | What it is |
| --- | --- |
| `skills/polar-sky-install/SKILL.md` | The skill: rules and the order of the phases |
| `skills/polar-sky-install/references/` | One file for each phase |
| `skills/polar-sky-install/scripts/` | Helper scripts: detection, value check, preflight checks, certificate check, and the Microsoft app registration's permission list and check |
| `plugins/polar-sky-status/` | The Polar Sky status mod for Claude Code, listed in `.claude-plugin/marketplace.json` |
| `plugins/polar-sky-access-reviews/` | Polar Sky's access review skills for Claude Code, the access review report and the audit trail, listed in `.claude-plugin/marketplace.json` |
| `recipes/` | Polar Sky's OpenTofu/Terraform recipes for a new GKE, EKS or AKS cluster; the skill downloads the one for your platform |

## Changes

This repository is a copy that Polar Sky publishes automatically. Changes are made in Polar Sky's main repository, where tests check the skill against the Polar Sky Install server, so pull requests here are not merged.

## License

Copyright Polar Sky Inc. All rights reserved. See [LICENSE](LICENSE).
