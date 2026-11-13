import { atom, read, update } from 'claude-code'
import type { McpToolResult, Register } from 'claude-code'

import type { Band, PolarSkyStatus } from '../types'

const band = atom({ plugin: 'polar-sky-status', key: 'band' } as const, null)

const MCP_TOOL = /^mcp__(.+)__([a-z_]+)$/i
const POLAR_SKY_NAME = /polar[-_ ]?sky/i
const STATUS_TOOL = 'get_status'
/** Tools only the Controls connector serves, so it is found whatever name it was added under. */
const CONTROLS_SIGNATURE = ['list_controls', 'get_control'] as const
/** Tools only the Install server serves, so it is found whatever name it was added under. */
const INSTALL_SIGNATURE = ['get_install_values', 'start_key_upload'] as const
const SHOWN_TIPS_KEY = 'shownTips'
const SHOWN_INSTALL_TIPS_KEY = 'shownInstallTips'
const BAR_CELLS = 16
// Polar Sky brand colors. Raw colors do not follow the person's theme, so each one reads on light and dark alike:
// the bar and the triangle are marks, labeled by the text beside them.
/** The customer's estate (ice): the folders are theirs. */
const CUSTOMER_COLOR = '#00B2E2'
/** state.blocked: a mark only, never type. */
const BLOCKED_COLOR = '#FF0B69'
/**
 * The Polar Sky logomark, where the surface draws SVG: brand ink on a light theme, white on a dark one. The surface
 * draws the SVG as an image, so it cannot take the theme's text color; it follows prefers-color-scheme instead.
 * Its size is in the markup, since the desktop draws an SVG with only a viewBox at no size, and its alt must not be
 * empty, since the desktop draws nothing for an Svg whose alt is.
 */
const LOGOMARK_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="21" height="32" viewBox="0 0 64.32 98.46">' +
  '<style>path{fill:#252529}@media (prefers-color-scheme:dark){path{fill:#FFFFFF}}</style>' +
  '<path d="M39.05.02L0,0v31.01c0,4.32,3.53,7.85,7.85,7.85h9.69c5.14,0,9.31,4.16,9.31,9.31v6.53h3.64v-6.53c0-5.14,4.17-9.31,9.31-9.31h6.53v-3.64h-6.53c-5.14,0-9.31-4.17-9.31-9.31v-6.53h-3.64v6.53c0,5.15-4.17,9.32-9.32,9.31h-4.6c-.87,0-1.57-.71-1.57-1.58v-11.74c.01-4.24-2.06-6.58-6.14-6.96v-3.25l33.83.11c7.45,0,13.49,6.04,13.49,13.49v23.72c0,7.45-6.04,13.49-13.49,13.49H7.89c-4.33,0-7.85,3.52-7.85,7.85l.05,28.11,11.72-.04v-24.14h27.24c13.95,0,25.27-11.31,25.27-25.27v-23.72C64.32,11.33,53,.02,39.05.02Z"/></svg>'

/** Tips the band rotates through, each naming a question the Polar Sky connectors answer. */
export const TIPS: readonly { id: string; text: string }[] = [
  { id: 'priority', text: 'Ask "which recommended control should I look at first?"' },
  { id: 'why', text: 'Ask "why did Polar Sky suggest this control?"' },
  { id: 'access-loss', text: 'Ask "who loses access if I approve this control?"' },
  { id: 'members', text: 'Ask "who keeps access to the folders this control covers?"' },
  { id: 'activity', text: 'Ask "what has changed on this control recently?"' },
  { id: 'reviewers', text: 'Ask "who could review this control with me?"' },
  { id: 'recent-use', text: 'Ask "is anyone losing access to files they opened in the last 90 days?"' },
  { id: 'carried', text: 'Ask "which controls need me to confirm an earlier decision?"' },
  { id: 'plan', text: 'Ask "how will Polar Sky apply this control if I approve it?"' },
  { id: 'remind', text: 'Ask "remind owners to review the controls assigned to them"' },
]

/** Tips the band rotates through during an install, each naming a question the install answers in both Cloud and On-Prem. */
export const INSTALL_TIPS: readonly { id: string; text: string }[] = [
  { id: 'remaining', text: 'Ask "what\'s left in my install?"' },
  { id: 'people', text: 'Ask "who else do I need to finish this install?"' },
  { id: 'permissions', text: 'Ask "which Google Workspace permissions does Polar Sky need, and why?"' },
  { id: 'keys', text: 'Ask "do my private keys ever leave this machine?"' },
  { id: 'drives', text: 'Ask "can I choose which shared drives Polar Sky monitors?"' },
  { id: 'failures', text: 'Ask "what does Polar Sky learn when a step fails?"' },
]

const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

/** Formats a count compactly, as 5K or 1.2M. */
export const formatCount = (count: number): string => compact.format(count)

/** Splits an MCP tool name into its server and tool, or returns null for a tool that is not an MCP tool. */
export const parseMcpTool = (name: string): { server: string; tool: string } | null => {
  const match = MCP_TOOL.exec(name)

  const [, server, tool] = match ?? []

  return server === undefined || tool === undefined ? null : { server, tool }
}

const findServer = (tools: readonly { name: string }[], signature: readonly string[]): string | null => {
  const byServer = new Map<string, Set<string>>()

  for (const { name } of tools) {
    const parsed = parseMcpTool(name)
    if (parsed !== null) {
      byServer.set(parsed.server, (byServer.get(parsed.server) ?? new Set()).add(parsed.tool))
    }
  }

  const found = [...byServer].find(([, served]) => signature.every(tool => served.has(tool)))

  return found?.[0] ?? null
}

/**
 * The Controls connector among the tools the model can call: the first server that serves its tools and get_status,
 * or null when none does.
 */
export const findControlsServer = (tools: readonly { name: string }[]): string | null =>
  findServer(tools, [...CONTROLS_SIGNATURE, STATUS_TOOL])

/** The Install server among the tools the model can call, or null when none serves its tools. */
export const findInstallServer = (tools: readonly { name: string }[]): string | null => findServer(tools, INSTALL_SIGNATURE)

/** Whether a call goes to a Polar Sky connector: the Controls connector, or any server named for Polar Sky. */
export const isPolarSkyServer = (server: string, controlsServer: string | null): boolean =>
  server === controlsServer || POLAR_SKY_NAME.test(server)

/** Reads the status payload from a get_status result, or returns null when it is missing or malformed. */
export const parseStatus = (result: McpToolResult): PolarSkyStatus | null => {
  if (result.isError) {
    return null
  }

  const text = result.content.find(block => block.type === 'text')
  const payload = result.structuredContent ?? (text && 'text' in text ? safeParse(String(text.text)) : null)

  return isStatus(payload) ? payload : null
}

const safeParse = (text: string): unknown => {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

const isCounts = (value: unknown, keys: readonly string[]): boolean =>
  typeof value === 'object' &&
  value !== null &&
  keys.every(key => typeof (value as Record<string, unknown>)[key] === 'number')

const isStatus = (value: unknown): value is PolarSkyStatus =>
  typeof value === 'object' &&
  value !== null &&
  isCounts((value as PolarSkyStatus).folders, ['scanned', 'sensitive', 'protected']) &&
  isCounts((value as PolarSkyStatus).controls, ['active', 'recommended', 'critical_recommended'])

/** Picks the first tip not yet shown, starting over once every tip has been shown. */
export const nextTip = (
  shown: readonly string[],
  tips: readonly { id: string; text: string }[] = TIPS,
): { tip: string; shown: string[] } => {
  const unseen = tips.find(tip => !shown.includes(tip.id))
  if (unseen !== undefined) {
    return { tip: unseen.text, shown: [...shown, unseen.id] }
  }

  const [first] = tips

  return first === undefined ? { tip: '', shown: [] } : { tip: first.text, shown: [first.id] }
}

/** Draws the protected share of sensitive folders as filled and empty cells. */
export const progressBar = (protectedFolders: number, sensitiveFolders: number): { filled: string; empty: string; percent: number } => {
  const ratio = sensitiveFolders === 0 ? 0 : Math.min(protectedFolders / sensitiveFolders, 1)
  const cells = Math.round(ratio * BAR_CELLS)

  return { filled: '█'.repeat(cells), empty: '░'.repeat(BAR_CELLS - cells), percent: Math.round(ratio * 100) }
}

type TipStore = { store: { get: (key: string) => Promise<unknown>; set: (key: string, value: unknown) => Promise<void> } }

async function takeTip($: TipStore, key: string, tips: readonly { id: string; text: string }[]): Promise<string> {
  const stored = await $.store.get(key)
  const shown = Array.isArray(stored) ? stored.filter((id): id is string => typeof id === 'string') : []
  const { tip, shown: updated } = nextTip(shown, tips)
  await $.store.set(key, updated)

  return tip
}

async function showBand($: Parameters<typeof update>[0], shown: Band, keep: (current: Band) => boolean): Promise<void> {
  await update($, band, current => (current !== null && keep(current) ? current : shown))
}

const succeeded = (result: { deny?: unknown; isError?: boolean }): boolean =>
  result.deny === undefined && result.isError !== true

export const register: Register = on => {
  let turn = 0
  let statusTurn = -1
  let installTurn = -1

  on('prompt.submit', async ($, e, next) => {
    turn += 1
    await update($, band, () => null)

    return next(e)
  })

  on('tool.call', { tool: MCP_TOOL }, async ($, e, next) => {
    const parsed = parseMcpTool(e.tool)

    if (parsed === null || parsed.tool === STATUS_TOOL || (statusTurn === turn && installTurn === turn)) {
      return next(e)
    }

    const shownFor = turn
    const servers = $.tool.list().then(tools => ({ install: findInstallServer(tools), controls: findControlsServer(tools) }))

    // Runs beside the call, so a call to any other MCP server waits only for the tool list.
    const showing = (async () => {
      const { install, controls } = await servers

      if (controls === null || parsed.server === install || !isPolarSkyServer(parsed.server, controls) || statusTurn === shownFor) {
        return
      }

      statusTurn = shownFor

      const status = parseStatus(await $.mcp.call(controls, STATUS_TOOL))

      if (status === null) {
        return
      }

      const tip = await takeTip($, SHOWN_TIPS_KEY, TIPS)

      if (shownFor === turn) {
        await showBand($, { status, tip }, () => false)
      }
    })().catch(() => undefined)

    const [result] = await Promise.all([next(e), showing])

    if (succeeded(result) && installTurn !== shownFor && parsed.server === (await servers.catch(() => null))?.install) {
      installTurn = shownFor

      const tip = await takeTip($, SHOWN_INSTALL_TIPS_KEY, INSTALL_TIPS).catch(() => '')

      if (tip !== '' && shownFor === turn) {
        await showBand($, { status: null, tip }, current => current.status !== null)
      }
    }

    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const shown = await read($, band)

    if (shown === null || e.props.hasSurvey) {
      return next(e)
    }

    const elements = $.ui.resolve(e)
    const { Box, Text } = elements
    const Svg = 'Svg' in elements ? elements.Svg : null
    const { status } = shown
    const bar = progressBar(status?.folders.protected ?? 0, status?.folders.sensitive ?? 0)

    return (
      <Box flexDirection="row">
        {Svg === null ? (
          <Box width={12}>
            <Text bold>Polar Sky</Text>
          </Box>
        ) : (
          <Box flexShrink={0} marginLeft={1} marginRight={2} justifyContent="center">
            <Svg source={LOGOMARK_SVG} alt="Polar Sky" />
          </Box>
        )}
        <Box flexDirection="column">
          {status === null ? null : (
            <Box flexDirection="column">
              <Box flexDirection="row">
                <Box width={10}>
                  <Text bold>Folders</Text>
                </Box>
                <Text dimColor>{formatCount(status.folders.scanned)} scanned, </Text>
                <Text>
                  {formatCount(status.folders.sensitive)} sensitive, {formatCount(status.folders.protected)} protected
                  {'  '}
                </Text>
                <Text color={CUSTOMER_COLOR}>{bar.filled}</Text>
                <Text dimColor>{bar.empty}</Text>
                <Text> {bar.percent}%</Text>
              </Box>
              <Box flexDirection="row">
                <Box width={10}>
                  <Text bold>Controls</Text>
                </Box>
                <Text>
                  {formatCount(status.controls.active)} active, {formatCount(status.controls.recommended)} recommended
                </Text>
                {status.controls.critical_recommended > 0 ? (
                  <Text>
                    {'  '}
                    <Text color={BLOCKED_COLOR}>▲</Text> {formatCount(status.controls.critical_recommended)} critical
                  </Text>
                ) : null}
              </Box>
            </Box>
          )}
          {shown.tip === '' ? null : <Text dimColor>Tip: {shown.tip}</Text>}
        </Box>
      </Box>
    )
  })
}
