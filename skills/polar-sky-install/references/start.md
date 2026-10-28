# Phase 1: Start

## Check the MCP server

Look for the Polar Sky Install tools: `get_install_values`, `request_certificate`, `start_key_upload` and `check_engine_connection`. If any of them is missing, the server is not connected. Stop, and give the person this command to run in their own terminal:

```bash
npx add-mcp@2.6.0 https://mcp.polarsky.ai/install -g
```

Then ask them to restart their agent and start again. Do not try to go on without the server.

The first call signs the person in to Polar Sky. Only an administrator of the organization can use these tools. If the answer says the person is not an administrator, or no organization is set up for their company domain, stop: tell them to contact their Polar Sky contact.

The first write call (`request_certificate` or `start_key_upload`) asks the person to approve write access. That is their choice; wait for it.

## Make the install folder

Show and run (it only creates an empty folder):

```bash
umask 077 && mkdir -p ~/polar-sky-install && cd ~/polar-sky-install && git rev-parse --show-toplevel 2>/dev/null || echo "not in a Git repository"
```

If the last line names a Git repository, stop: ask the person for another folder, outside any repository, and use it in place of `~/polar-sky-install` everywhere.

## Get the install values

Call `get_install_values`. Write each value from the answer into `~/polar-sky-install/values.env`, one `export NAME='value'` line each, with the names below. Copy every value exactly as the tool gave it. If the answer has a value not in this table, add it as `POLAR_SKY_` plus its field name in capitals with `_` between words. Do not write the request ID or `refused`. Leave out every value that is empty or null.

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

`<skill folder>` is the folder this `SKILL.md` is in. If the script reports a problem, show it to the person and stop: a missing or wrong value comes from Polar Sky, so they contact their Polar Sky contact.

Show the person the organization name, and ask them to confirm this is the right organization. The deployment platform (`POLAR_SKY_INFRA_PROFILE`) is not in these values: phase 2 finds it.
