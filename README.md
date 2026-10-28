# Polar Sky install skill

## For AI agents

If a person asked you to install Polar Sky from this repository, do these three steps.

1. **Add the Polar Sky Install MCP server.** Its address is `https://mcp.polarsky.ai/install`. It uses streamable HTTP and OAuth sign-in. In Claude Code, run:

   ```bash
   claude mcp add --transport http polar-sky-install https://mcp.polarsky.ai/install
   ```

   In another agent, use that agent's own way to add a remote MCP server, or run `npx add-mcp@<pinned version> https://mcp.polarsky.ai/install -g`.
2. **Get the skill.** If you can install skills, run `npx skills@<pinned version> add polarskyinc/install -g`. If you cannot, read [`skills/polar-sky-install/SKILL.md`](skills/polar-sky-install/SKILL.md) in this repository and follow it, with the files it links to.
3. **Start.** Tell the person that they may need to restart you before the MCP server loads. Then start phase 1 of the skill.

The skill's hard rules apply from the first command. Read them in the "Hard rules" section of `SKILL.md` before you run anything.

## What this is

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
npx add-mcp@<pinned version> https://mcp.polarsky.ai/install -g
npx skills@<pinned version> add polarskyinc/install -g
```

The first command connects your agent to the Polar Sky Install server. The second adds the skill.

## Use

Ask your agent: "Install Polar Sky". The skill starts by signing you in to Polar Sky and reading your organization's install values.

The skill never prints your private keys, service account keys or Kubernetes secrets, and never puts them in the chat. It sends Polar Sky public things: the certificate signing request, service account emails, client IDs and the Workspace admin email. The one secret Polar Sky receives is the cloud service account key, which the skill uploads once with `curl`, straight from the file, with a one-time upload token; Polar Sky stores it encrypted, and the skill then deletes the file.

## What is in this repository

| Path | What it is |
| --- | --- |
| `skills/polar-sky-install/SKILL.md` | The skill: rules and the order of the phases |
| `skills/polar-sky-install/references/` | One file for each phase |
| `skills/polar-sky-install/scripts/` | Helper scripts: detection, value check, preflight checks, certificate check |

## Changes

This repository is a copy that Polar Sky publishes automatically. Changes are made in Polar Sky's main repository, where tests check the skill against the Polar Sky Install server, so pull requests here are not merged.

## License

Copyright Polar Sky Inc. All rights reserved. See [LICENSE](LICENSE).
