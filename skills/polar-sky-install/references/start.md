# Phase 1: Start

## Open the install

Before your first command, tell the person one line: "First, I'll look around this machine without changing anything." Say no other line about it. Then do the look around below, and give the preview. The install has three steps: the preview, the questions, and the final plan for one approval.

## Check the MCP server

Look for the Polar Sky Install tools: `get_install_values`, `request_certificate`, `check_engine_connection`, `start_key_upload`, `start_microsoft365_upload`, `start_okta_connection`, `finish_okta_connection` and `report_issue`. If any of them is missing, the server is not connected. Find out why before you give the person anything to run. In Claude Code, `claude mcp list` (read only) shows each registered server and its state.

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

The first write call (`request_certificate`, `start_key_upload`, `start_microsoft365_upload` or `start_okta_connection`) asks the person to approve write access. That is their choice; wait for it.

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

## Look around

Look around so the preview fits this organization. Everything here only reads. Do not tell the person about it again: the opening line already did.

Call `get_install_values` with no `deployment_model`. It only reads. It answers for On-Prem, the default, and tells you whether the organization already has an engine, in `has_engine`, and whether a provider is connected: `google_workspace_connected`, and `microsoft365_connected` with the tenant in `microsoft365_tenant_id`. Write no value from this answer yet.

Run the detection script with no argument. It only reads, and prints the tools and sign-ins on this machine, including the `az` account and tenant:

```bash
<skill folder>/scripts/detect.sh
```

Also use what you already know about the company from this conversation, such as its name or the Google or Microsoft 365 domain the person mentions. Do not ask about it yet.

Do not explain or act on the cluster lines yet: the person may choose Cloud, which has no cluster, or Microsoft 365, which needs no gcloud. If a sign-in shows as expired, only note it. Do not ask for a fix yet: the questions step asks for it once the model is known, as in [Look up what the model needs](discover.md).

## Preview the install

Write one message, in this order. Ask nothing in it except the question at the end.

1. **What Polar Sky is,** in two or three sentences, for example:

   > Polar Sky is a data protection agent. AI assistants can read everything a person can reach, and most people can reach far more than they need. Polar Sky works out who needs to see what, finds overexposed files, and proposes controls your team approves.

2. **Where the organization's files are,** Google Workspace or Microsoft 365. Polar Sky connects one of them per organization:
   - **If `google_workspace_connected` is true,** Google Workspace is already connected. Say so, and give only the Google Workspace steps. Do not offer Microsoft 365.
   - **If `microsoft365_connected` is true,** Microsoft 365 is already connected, for the tenant in `microsoft365_tenant_id`. Say so, and give only the Microsoft 365 steps. Do not offer Google Workspace.
   - **Otherwise,** say Polar Sky works with either. Put a signal first when there is one, for example an `az` sign-in, or a gcloud account, in the company's domain: "Your Azure CLI is signed in to the contoso.com tenant, so I expect Microsoft 365."

3. **The deployment models,** in plain words:
   - **If `has_engine` is true,** the organization already runs Polar Sky's On-Prem deployment, with an engine in its own cluster. Say so, and do not offer Cloud.
   - **If `has_engine` is false,** give both, one plain line each, and do not recommend either one:
     - **Cloud:** Polar Sky Cloud reads file content, and nothing runs in your cloud.
     - **On-Prem:** an engine in your own Kubernetes cluster reads file content, so Polar Sky Cloud never sees it. It needs a Kubernetes cluster with GPUs.

4. **The steps and how long each usually takes,** for the provider and the models you offered. When nothing points to a provider, give the Google Workspace steps and the Microsoft 365 steps. Say which people they need:
   - **Google Workspace:** a Google Workspace super admin, for a few minutes, and an Okta super admin if the company manages its groups in Okta. In both models, Okta adds one step, before connecting Google Workspace: Polar Sky connects to Okta through an Okta app whose key only Polar Sky holds, so it can create the groups for approved controls there.
   - **Microsoft 365:** a Global Administrator or Privileged Role Administrator of the Microsoft 365 tenant, for a few minutes, to grant admin consent. The person who creates the app registrations must be allowed to register applications, which Microsoft Entra ID allows every user by default. Audit logging must be on in Microsoft Purview. There is no Okta step for Microsoft 365.
   - **Both:** only for the optional Slack step, someone who may add apps to the company's Slack, or a Slack admin to approve the Polar Sky app.

   Google Workspace, Cloud:

   | Step | Usually takes |
   | --- | --- |
   | Sign in to Polar Sky, look at this machine and your Google Cloud project, and agree the plan | 5 to 10 minutes |
   | Create the Google service account, and a super admin approves its access | 10 minutes, plus the super admin's time |
   | Only when your groups live in Okta: connect Okta | 10 to 15 minutes, with an Okta super admin |
   | Connect Google Workspace and choose what Polar Sky monitors | 10 minutes |
   | Optional, only when your company uses Slack: connect Slack, so Polar Sky's messages arrive there | 5 minutes, plus a Slack admin's approval if your Slack needs one |

   Google Workspace, On-Prem:

   | Step | Usually takes |
   | --- | --- |
   | Sign in to Polar Sky, look at this machine and your cloud, and agree the plan | 5 to 10 minutes |
   | Create the Google service accounts, and a super admin approves their access | 10 minutes, plus the super admin's time |
   | Set up the Kubernetes cluster the engine runs on | 15 to 30 minutes for a new cluster |
   | Get the engine's certificate and install the engine | 20 to 30 minutes, mostly loading AI models |
   | Only when your groups live in Okta: connect Okta | 10 to 15 minutes, with an Okta super admin |
   | Connect Google Workspace and choose what Polar Sky monitors | 10 minutes |
   | Optional, only when your company uses Slack: connect Slack, so Polar Sky's messages arrive there | 5 minutes, plus a Slack admin's approval if your Slack needs one |

   Microsoft 365, Cloud:

   | Step | Usually takes |
   | --- | --- |
   | Sign in to Polar Sky, look at this machine and your Microsoft 365 tenant, and agree the plan | 5 to 10 minutes |
   | Create the Polar Sky app registration in Microsoft Entra ID, and an administrator grants its access | 10 minutes, plus the administrator's time |
   | Connect Microsoft 365 | 5 to 10 minutes |
   | Optional, only when your company uses Slack: connect Slack, so Polar Sky's messages arrive there | 5 minutes, plus a Slack admin's approval if your Slack needs one |

   Microsoft 365, On-Prem:

   | Step | Usually takes |
   | --- | --- |
   | Sign in to Polar Sky, look at this machine, your Microsoft 365 tenant and your cloud, and agree the plan | 5 to 10 minutes |
   | Create the two Polar Sky app registrations in Microsoft Entra ID, and an administrator grants their access | 15 minutes, plus the administrator's time |
   | Set up the Kubernetes cluster the engine runs on | 15 to 30 minutes for a new cluster |
   | Get the engine's certificate and install the engine | 20 to 30 minutes, mostly loading AI models |
   | Connect Microsoft 365 | 10 minutes |
   | Optional, only when your company uses Slack: connect Slack, so Polar Sky's messages arrive there | 5 minutes, plus a Slack admin's approval if your Slack needs one |

   In Cloud, the super admin's or administrator's approval is the longest wait. In On-Prem, the service accounts or app registrations and the cluster can be set up at the same time, so the approval does not hold up the rest.

5. **The question, as the last line.** When no provider is connected and `has_engine` is false, end with: "Does your organization use Google Workspace or Microsoft 365, and which deployment does it want: On-Prem in your own cluster, or Cloud?" When a provider is connected and `has_engine` is false, end with: "Which deployment does your organization want: On-Prem in your own cluster, or Cloud?" Keep that order: some assistants suggest a reply from the last option, and pressing Enter on a suggested On-Prem would start the longer install with a cluster by mistake. If `has_engine` is true, end with: "Shall I go ahead with the On-Prem install?"

The preview sets expectations only. It is not the plan and needs no approval.

When the answer comes:

- **The provider.** Record the provider the person names: `google_workspace` for Google Workspace, `microsoft365` for Microsoft 365. When a provider is connected, it is that one. When the person names only the deployment and the signals point to one provider, use it, and say which one in the questions message, so the person can correct it. Otherwise ask which one in a short message of its own, and wait for the answer: the install values below depend on it. If the person names the provider that is not connected while the other one is, tell them: "Polar Sky connects one provider per organization, and yours already has the other one connected, so I cannot connect this one here. I will tell Polar Sky, so they can help." Then call `report_issue`, as in [Report issues](../SKILL.md#report-issues), and stop.
- **The deployment.** If `has_engine` is true and the person wants Cloud, tell them: "Moving an organization that has an engine to Cloud is not part of this install, so I cannot do it here. I will tell Polar Sky, so they can help." Then call `report_issue` and stop. Otherwise record the model the person names, `cloud` for Cloud or `on_prem` for On-Prem.

Then make the install folder and get the install values for that provider and model, as below. These steps only create files and read values, so they run without a yes. After them, go on to the questions in [Look up what the model needs](discover.md).

## Make the install folder

Show and run (it only creates an empty folder):

```bash
umask 077 && mkdir -p ~/polar-sky-install && cd ~/polar-sky-install && git rev-parse --show-toplevel 2>/dev/null || echo "not in a Git repository"
```

If the last line names a Git repository, stop: ask the person for another folder, outside any repository, and use it in place of `~/polar-sky-install` everywhere.

## Get the install values

Call `get_install_values` with `deployment_model` set to the model the person chose: `cloud` or `on_prem`. For Microsoft 365, also pass `provider` `microsoft365`. Write each value from that answer into `~/polar-sky-install/values.env`, one `export NAME='value'` line each, with the names below. Copy every value exactly as the tool gave it. Do not write `has_engine`, `scopes` or the request ID, and do not write `refused`. The `scopes` list explains each delegation scope for the person; do not write it to the file. Do not write `okta_connected`, `okta_org_url`, `provisioning_mode`, `managed_group_materialization` or `managed_group_prefix` either: they tell you whether Okta is connected and how groups are set up, for the questions and phase 8. A `provisioning_mode` of `okta` without Okta connected is the normal default, not a problem: see the Okta question in [Look up what the model needs](discover.md). Do not write `slack_connected` or `slack_workspace_name`: they tell you whether Slack is connected, for the questions and the [Slack step](slack.md). Do not write `google_workspace_connected`, `microsoft365_connected`, `microsoft365_tenant_id`, `microsoft365_client_id`, `microsoft365_reading` or `microsoft365_credential` either: they say which provider is connected and how reading goes, for the preview, the questions and the connection step. Write `microsoft365_permissions` not to `values.env` but, exactly as given, as one JSON array, to the public file `~/polar-sky-install/microsoft-permissions.json` with your file tool: the app registration step reads its permissions from there. If the answer has any other value not in this table, add it as `POLAR_SKY_` plus its field name in capitals with `_` between words. Leave out every value that is empty or null.

| Name | Value from `get_install_values` | Models |
| --- | --- | --- |
| `POLAR_SKY_PROVIDER` | The provider the person chose, `google_workspace` or `microsoft365` | Both |
| `POLAR_SKY_DEPLOYMENT_MODEL` | The model the person chose, `cloud` or `on_prem` | Both |
| `POLAR_SKY_ORGANIZATION_ID` | The organization ID | Both |
| `POLAR_SKY_ORGANIZATION_NAME` | The organization name | Both |
| `POLAR_SKY_CONSOLE_URL` | The Polar Sky console address | Both |
| `POLAR_SKY_CLOUD_SCOPES` | The delegation scopes for the cloud service account, as one comma-separated line. In Cloud, this is the `cloud_scopes` answer | Both, Google Workspace only |
| `POLAR_SKY_CHART_VERSION` | The Polar Sky chart version | On-Prem |
| `POLAR_SKY_RELEASE_CHANNEL` | The release channel, `latest` | On-Prem |
| `POLAR_SKY_CHART_REFERENCE` | The Polar Sky chart address | On-Prem |
| `POLAR_SKY_HOST` | The Polar Sky Cloud endpoint the engine connects to | On-Prem |
| `POLAR_SKY_ON_PREM_SCOPES` | The delegation scopes for the on-premises service account, as one comma-separated line | On-Prem, Google Workspace only |

A Cloud answer has no chart, chart address, host or on-premises values, so write none of them. A Microsoft 365 answer has no scope lines, so write none of them either.

In On-Prem, also add this line, which is the same for every On-Prem install:

```bash
export POLAR_SKY_NAMESPACE='polar-sky-on-prem'
```

A Cloud install has no namespace, so do not add this line to it.

A value with a single quote (`'`) in it cannot go in this file safely. If one has it, stop and tell the person to contact Polar Sky.

Write the file with your file tool, not with `echo`. Then check it. The script only reads the file, and prints each value and every problem at once:

```bash
. ~/polar-sky-install/values.env && <skill folder>/scripts/check-values.sh
```

`<skill folder>` is the folder this `SKILL.md` is in. When you show a command, put the real path in place of `<skill folder>`, so the person sees exactly what runs. If the script reports a problem, show it to the person and stop: a missing or wrong value comes from Polar Sky, so they contact their Polar Sky contact.

Tell the person which organization they are signed in to, by name, for example "You are signed in to Polar Sky as **Acme Corp**." They confirm it with the final plan in phase 2. Do not mention the values file or the check. In On-Prem, the deployment platform (`POLAR_SKY_INFRA_PROFILE`) is not in these values: phase 2 finds it.
