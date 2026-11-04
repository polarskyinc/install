# Phase 1: Start

## Open the install

Before your first command, tell the person in two or three sentences what Polar Sky is and what this install sets up. For example:

> Polar Sky is a data protection agent. AI assistants can read everything a person can reach, and most people can reach far more than they need. Polar Sky works out who needs to see what, finds overexposed files, and proposes controls your team approves.

Then give a short picture of the setup, in a few lines:

- **The engine runs in your own cloud,** in a Kubernetes cluster with GPU nodes. It reads your files there, with AI models that run in the cluster.
- **Polar Sky Cloud gets the results,** and reads users, groups and sharing. It never sees the raw content of your files.
- **Google Workspace connects through two service accounts** in your Google Cloud project, one for the engine and one for Polar Sky Cloud. A Workspace super admin approves their access. No one's password is used.
- **Who else you may need:** a Workspace super admin, for a few minutes.

Then show the steps and how long each usually takes, so the person can plan:

| Step | Usually takes |
| --- | --- |
| Sign in to Polar Sky, look at this machine and your cloud, and agree the plan | 5 to 10 minutes |
| Create the Google service accounts, and a super admin approves their access | 10 minutes, plus the super admin's time |
| Set up the Kubernetes cluster the engine runs on | 15 to 30 minutes for a new cluster |
| Get the engine's certificate and install the engine | 20 to 30 minutes, mostly loading AI models |
| Connect Google Workspace and choose what Polar Sky monitors | 10 minutes |

Say that the service accounts and the cluster can be set up at the same time, so the super admin's approval does not hold up the rest. Say you will show every command, and ask once for the whole plan and once for each step. Then start.

## Check the MCP server

Look for the Polar Sky Install tools: `get_install_values`, `request_certificate`, `check_engine_connection`, `start_key_upload` and `report_issue`. If any of them is missing, the server is not connected. Find out why before you give the person anything to run. In Claude Code, `claude mcp list` (read only) shows each registered server and its state.

If it lists `polar-sky-install` as disabled for this project (`Disabled for this project (re-enable via /mcp)`), the server is registered but turned off in this folder. Tell the person to type `/mcp`, choose `polar-sky-install` and turn it back on, then **Authenticate** if it asks. Do not add it again.

If it is not listed, stop, and give the person the command for the agent you are, to run in their own terminal. In Claude Code:

```bash
claude mcp add --scope user --transport http polar-sky-install https://mcp.polarsky.ai/install
```

In Codex:

```bash
codex mcp add polar-sky-install --url https://mcp.polarsky.ai/install
```

Give it on one line, as shown. In Claude Code, they then type `/mcp`: if `polar-sky-install` is listed there, they choose it and **Authenticate**, and the tools load in this conversation without a restart; look for them again. If it is not listed, or in Codex, tell them how to restart you and keep this conversation: in Claude Code, type `/exit`, then run `claude --continue` in the same folder; in Codex, quit, then run `codex resume --last` in the same folder. After the restart, they sign in as described below and say "Install Polar Sky" again. Do not try to go on without the server.

The first call signs the person in to Polar Sky. If the tools are listed but the server asks for sign-in, tell the person how to start it: in Claude Code, type `/mcp`, choose `polar-sky-install` and **Authenticate**; in Codex, run `codex mcp login polar-sky-install` in a terminal. Both open Polar Sky's sign-in page in the browser. Only an administrator of the organization can use these tools. If the answer says the person is not an administrator, or no organization is set up for their company domain, stop: tell them to contact their Polar Sky contact.

The first write call (`request_certificate` or `start_key_upload`) asks the person to approve write access. That is their choice; wait for it.

## Check that your commands can reach the network

The install downloads from GitHub and calls the cloud, Helm and Terraform registries, so your shell commands need network access. Polar Sky tools can work while your shell has none. Show and run (it only reads):

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://github.com
```

A number such as `200` or `301` means the network works. An error such as `Could not resolve host` or `Operation not permitted` means your sandbox blocks it.

If you are Codex and the network is blocked, stop. Do not work around it with other tools, connectors or another folder. Tell the person: "Codex's sandbox blocks network access for my commands, and the install needs it. Quit Codex (press Ctrl+C twice), then run this command in the same folder. It opens this conversation again with network access, and I will continue from here." Then give this command on one line:

```bash
umask 077 && mkdir -p ~/polar-sky-install ~/.kube ~/.config/gcloud && codex resume --last -a on-request -c sandbox_workspace_write.network_access=true --add-dir ~/polar-sky-install --add-dir ~/.kube --add-dir ~/.config/gcloud
```

It keeps Codex's sandbox and lets your commands reach the network and write to the install folder, the kubeconfig and the gcloud settings. `-a on-request` lets you ask the person before a command goes outside the sandbox. If Codex says the conversation is open in another app, the old Codex is still running: they quit it fully and run the command again.

If you are another agent and the network is blocked, tell the person what failed and ask them to allow network access for your commands, then run the check again.

Later in the install, if a command fails the same way, or cannot write to `~/polar-sky-install`, `~/.kube` or the gcloud settings, stop and do the same. Never move the install folder somewhere else to get around it.

## Make the install folder

Show and run (it only creates an empty folder):

```bash
umask 077 && mkdir -p ~/polar-sky-install && cd ~/polar-sky-install && git rev-parse --show-toplevel 2>/dev/null || echo "not in a Git repository"
```

If the last line names a Git repository, stop: ask the person for another folder, outside any repository, and use it in place of `~/polar-sky-install` everywhere.

## Get the install values

Call `get_install_values`. Write each value from the answer into `~/polar-sky-install/values.env`, one `export NAME='value'` line each, with the names below. Copy every value exactly as the tool gave it. The `scopes` list explains each delegation scope for the person; do not write it to the file. If the answer has any other value not in this table, add it as `POLAR_SKY_` plus its field name in capitals with `_` between words. Do not write the request ID or `refused`. Leave out every value that is empty or null.

| Name | Value from `get_install_values` |
| --- | --- |
| `POLAR_SKY_ORGANIZATION_ID` | The organization ID |
| `POLAR_SKY_ORGANIZATION_NAME` | The organization name |
| `POLAR_SKY_CHART_VERSION` | The Polar Sky chart version |
| `POLAR_SKY_RELEASE_CHANNEL` | The release channel, `latest` |
| `POLAR_SKY_HOST` | The Polar Sky Cloud endpoint the engine connects to |
| `POLAR_SKY_CONSOLE_URL` | The Polar Sky console address |
| `POLAR_SKY_CLOUD_SCOPES` | The delegation scopes for the cloud service account, as one comma-separated line |
| `POLAR_SKY_ON_PREM_SCOPES` | The delegation scopes for the on-premises service account, as one comma-separated line |

Also add this line, which is the same for every install:

```bash
export POLAR_SKY_NAMESPACE='polar-sky-on-prem'
```

A value with a single quote (`'`) in it cannot go in this file safely. If one has it, stop and tell the person to contact Polar Sky.

Write the file with your file tool, not with `echo`. Then check it. The script only reads the file, and prints each value and every problem at once:

```bash
. ~/polar-sky-install/values.env && <skill folder>/scripts/check-values.sh
```

`<skill folder>` is the folder this `SKILL.md` is in. When you show a command, put the real path in place of `<skill folder>`, so the person sees exactly what runs. If the script reports a problem, show it to the person and stop: a missing or wrong value comes from Polar Sky, so they contact their Polar Sky contact.

Tell the person which organization they are signed in to, by name, for example "You are signed in to Polar Sky as **Acme Corp**." They confirm it with the install plan in phase 2. Do not mention the values file or the check. The deployment platform (`POLAR_SKY_INFRA_PROFILE`) is not in these values: phase 2 finds it.
