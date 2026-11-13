# Polar Sky status mod for Claude Code

Once Claude calls a Polar Sky connector, this mod shows a band above the prompt with your organization's current status and a tip. In the Claude desktop app the band starts with the Polar Sky logomark; in the terminal it starts with "Polar Sky".

```
 Polar Sky  Folders   5K scanned, 200 sensitive, 40 protected  ███░░░░░░░░░░░░░ 20%
            Controls  12 active, 5 recommended  ▲ 2 critical
            Tip: Ask "who loses access if I approve this control?"
```

During an install, a call to the Polar Sky Install server shows a tip about the install instead, with no counts:

```
 Polar Sky  Tip: Ask "what's left in my install?"
```

## Install

In Claude Code, run:

```
/plugin install polar-sky-status --marketplace polarskyinc/install
```

The mod needs the Polar Sky Controls connector. It reads the numbers from the connector's `get_status` tool once per turn. In auto mode, allow that tool so the band can read it without asking, for example with this rule in `permissions.allow` in your Claude Code settings, using the server name your Controls connector has:

```
mcp__<controls server>__get_status
```

## How it works

The mod finds the Controls connector by the tools it serves (`list_controls`, `get_control` and `get_status`), so it works whatever name the connector was added under. A call to the Controls connector, or to any server named for Polar Sky such as the Google Drive connector, shows the band. The band stays up after the reply until your next message, and does not show when the status cannot be read.

The mod finds the Install server the same way, by `get_install_values` and `start_key_upload`. A call to it shows an install tip without reading the status, so the install band does not need the Controls connector. Install tips and control tips rotate separately.

Check it with `claude plugin validate plugins/polar-sky-status` and `claude plugin test plugins/polar-sky-status`.
