import { expect, test } from 'claude-code/testing'

import {
  findControlsServer,
  findInstallServer,
  formatCount,
  INSTALL_TIPS,
  isPolarSkyServer,
  nextTip,
  parseMcpTool,
  progressBar,
  TIPS,
} from '../hooks/register'

const STATUS = {
  folders: { scanned: 5000, sensitive: 200, protected: 40 },
  controls: { active: 12, recommended: 5, critical_recommended: 2 },
}

const settle = async () => {
  for (let tick = 0; tick < 50; tick += 1) {
    await Promise.resolve()
  }
}

const TOOLS = [
  { name: 'mcp__claude_ai_Polar_Sky_Controls__list_controls', description: '', mcp: true },
  { name: 'mcp__claude_ai_Polar_Sky_Controls__get_control', description: '', mcp: true },
  { name: 'mcp__claude_ai_Polar_Sky_Controls__get_status', description: '', mcp: true },
  { name: 'mcp__claude_ai_Polar_Sky_Google_Drive__search_files', description: '', mcp: true },
]

/** The Controls connector as an ID-named server, the way it is added in the desktop app. */
const CONNECTOR_ID = '8dbfc99a-af2a-4dc1-ad8f-dbafdc816816'

const ID_TOOLS = [
  { name: `mcp__${CONNECTOR_ID}__list_controls`, description: '', mcp: true },
  { name: `mcp__${CONNECTOR_ID}__get_control`, description: '', mcp: true },
  { name: `mcp__${CONNECTOR_ID}__get_status`, description: '', mcp: true },
  { name: 'mcp__claude_ai_Gmail__create_draft', description: '', mcp: true },
]

const INSTALL_TOOLS = [
  { name: 'mcp__polar-sky-install__get_install_values', description: '', mcp: true },
  { name: 'mcp__polar-sky-install__start_key_upload', description: '', mcp: true },
  ...TOOLS,
]

const BAND = {
  plugin: 'polar-sky-status',
  component: 'AbovePrompt',
  surface: 'terminal',
  props: { hasSurvey: false, isWorking: true, maxRows: 6, bodyColumns: 120, scroll: { offset: 0, bodyRows: 6 }, view: {} },
} as const

test('the band stays up after the reply, until the next message', async ($, on) => {
  const calls: string[] = []

  on('mcp.call', (_, e) => {
    calls.push(`${e.server}/${e.tool}`)

    return { value: { content: [{ type: 'text', text: JSON.stringify(STATUS) }], isError: false } }
  })
  on('tool.list', () => ({ value: TOOLS }))
  on('store.get', () => ({ value: undefined }))
  on('store.set', () => ({ value: undefined }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })
  on('tool.call', () => ({ result: {} }))
  on('turn.complete', () => ({ text: '' }))
  on('prompt.submit', (_, e) => ({ text: e.text }))

  await $.tool.call({ tool: 'mcp__claude_ai_Polar_Sky_Google_Drive__search_files' })
  await $.tool.call({ tool: 'mcp__claude_ai_Polar_Sky_Controls__list_controls' })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text', text: /sensitive/ }))?.text).toContain('200 sensitive, 40 protected')
  expect((await ui.find({ type: 'Text', text: /critical/ }))?.text).toContain('▲ 2 critical')
  expect((await ui.find({ type: 'Text', text: /^Tip:/ }))?.text).toBe(`Tip: ${TIPS[0]?.text}`)
  expect(calls).toEqual(['claude_ai_Polar_Sky_Controls/get_status'])
  await ui.unmount()

  await $.turn.complete({ reason: 'answer', answer: '', durationMs: 1000, isAborted: false, turnId: 'turn-1' })

  const idle = await $.ui.mount({ ...BAND, props: { ...BAND.props, isWorking: false } })
  expect((await idle.find({ type: 'Text', text: /sensitive/ }))?.text).toContain('200 sensitive')
  await idle.unmount()

  await $.prompt.submit({ text: 'thanks', wait: false, origin: { kind: 'composer' } })

  const after = await $.ui.mount({ ...BAND, props: { ...BAND.props, isWorking: false } })
  expect(await after.find({ type: 'Text', text: /sensitive/ })).toBe(undefined)
  await after.unmount()
})

test('other tools and the status tool itself do not show the band', async ($, on) => {
  const calls: string[] = []

  on('mcp.call', (_, e) => {
    calls.push(e.tool)

    return { value: { content: [], isError: false } }
  })
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await $.tool.call({ tool: 'mcp__claude_ai_Polar_Sky_Controls__get_status' })

  expect(calls).toEqual([])
})

test('a failed status call shows no band', async ($, on) => {
  let finishCall: () => void = () => undefined

  on('tool.list', () => ({ value: TOOLS }))
  on('mcp.call', () => ({ value: { content: [{ type: 'text', text: 'denied' }], isError: true } }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })
  on('tool.call', () => new Promise(resolve => (finishCall = () => resolve({ result: {} }))))

  const running = $.tool.call({ tool: 'mcp__claude_ai_Polar_Sky_Google_Drive__search_files' })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: /sensitive/ })).toBe(undefined)
  await ui.unmount()

  finishCall()
  await running
})

test('a Controls connector whose name does not say Polar Sky shows the band', async ($, on) => {
  const calls: string[] = []

  on('mcp.call', (_, e) => {
    calls.push(`${e.server}/${e.tool}`)

    return { value: { content: [{ type: 'text', text: JSON.stringify(STATUS) }], isError: false } }
  })
  on('tool.list', () => ({ value: ID_TOOLS }))
  on('store.get', () => ({ value: undefined }))
  on('store.set', () => ({ value: undefined }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: 'mcp__claude_ai_Gmail__create_draft' })
  await settle()
  expect(calls).toEqual([])

  await $.tool.call({ tool: `mcp__${CONNECTOR_ID}__list_controls` })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text', text: /sensitive/ }))?.text).toContain('200 sensitive, 40 protected')
  expect(calls).toEqual([`${CONNECTOR_ID}/get_status`])
  await ui.unmount()
})

test('a Controls connector without get_status shows no band and calls nothing', async ($, on) => {
  const calls: string[] = []

  on('mcp.call', (_, e) => {
    calls.push(e.tool)

    return { value: { content: [], isError: true } }
  })
  on('tool.list', () => ({ value: ID_TOOLS.filter(tool => !tool.name.endsWith('get_status')) }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: `mcp__${CONNECTOR_ID}__list_controls` })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: /sensitive/ })).toBe(undefined)
  expect(calls).toEqual([])
  await ui.unmount()
})

test('an install call shows an install tip with no counts and calls nothing', async ($, on) => {
  const calls: string[] = []

  on('mcp.call', (_, e) => {
    calls.push(e.tool)

    return { value: { content: [{ type: 'text', text: JSON.stringify(STATUS) }], isError: false } }
  })
  on('tool.list', () => ({ value: INSTALL_TOOLS }))
  on('store.get', () => ({ value: undefined }))
  on('store.set', () => ({ value: undefined }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: 'mcp__polar-sky-install__get_install_values' })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text', text: /^Tip:/ }))?.text).toBe(`Tip: ${INSTALL_TIPS[0]?.text}`)
  expect(await ui.find({ type: 'Text', text: /sensitive/ })).toBe(undefined)
  expect(calls).toEqual([])
  await ui.unmount()
})

const mountInstallTurn = (on: Parameters<Parameters<typeof test>[1]>[1], calls: string[]) => {
  on('mcp.call', (_, e) => {
    calls.push(e.tool)

    return { value: { content: [{ type: 'text', text: JSON.stringify(STATUS) }], isError: false } }
  })
  on('tool.list', () => ({ value: INSTALL_TOOLS }))
  on('store.get', () => ({ value: undefined }))
  on('store.set', () => ({ value: undefined }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })
}

test('a Controls call after an install call in the same turn shows the counts', async ($, on) => {
  const calls: string[] = []

  mountInstallTurn(on, calls)
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: 'mcp__polar-sky-install__get_install_values' })
  await settle()
  await $.tool.call({ tool: 'mcp__claude_ai_Polar_Sky_Controls__list_controls' })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text', text: /sensitive/ }))?.text).toContain('200 sensitive')
  expect(calls).toEqual(['get_status'])
  await ui.unmount()
})

test('an install call after a Controls call in the same turn keeps the counts', async ($, on) => {
  const calls: string[] = []

  mountInstallTurn(on, calls)
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: 'mcp__claude_ai_Polar_Sky_Controls__list_controls' })
  await settle()
  await $.tool.call({ tool: 'mcp__polar-sky-install__get_install_values' })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text', text: /sensitive/ }))?.text).toContain('200 sensitive')
  expect((await ui.find({ type: 'Text', text: /^Tip:/ }))?.text).toBe(`Tip: ${TIPS[0]?.text}`)
  await ui.unmount()
})

test('a refused install call shows no band', async ($, on) => {
  const calls: string[] = []

  mountInstallTurn(on, calls)
  on('tool.call', () => ({ deny: 'insufficient_scope' }))

  await $.tool.call({ tool: 'mcp__polar-sky-install__get_install_values' })
  await settle()

  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: /^Tip:/ })).toBe(undefined)
  expect(calls).toEqual([])
  await ui.unmount()
})

test('helpers', () => {
  expect(parseMcpTool('mcp__claude_ai_Polar_Sky_Google_Drive__search_files')).toEqual({
    server: 'claude_ai_Polar_Sky_Google_Drive',
    tool: 'search_files',
  })
  expect(parseMcpTool(`mcp__${CONNECTOR_ID}__list_controls`)).toEqual({ server: CONNECTOR_ID, tool: 'list_controls' })
  expect(parseMcpTool('Bash')).toBe(null)

  expect(findControlsServer(TOOLS)).toBe('claude_ai_Polar_Sky_Controls')
  expect(findControlsServer(ID_TOOLS)).toBe(CONNECTOR_ID)
  expect(findControlsServer(ID_TOOLS.filter(tool => !tool.name.endsWith('get_status')))).toBe(null)
  expect(findControlsServer([{ name: 'mcp__claude_ai_Gmail__create_draft' }])).toBe(null)

  expect(findInstallServer(INSTALL_TOOLS)).toBe('polar-sky-install')
  expect(findInstallServer(TOOLS)).toBe(null)

  expect(isPolarSkyServer(CONNECTOR_ID, CONNECTOR_ID)).toBe(true)
  expect(isPolarSkyServer('claude_ai_Polar_Sky_Google_Drive', null)).toBe(true)
  expect(isPolarSkyServer('claude_ai_Gmail', CONNECTOR_ID)).toBe(false)

  expect(formatCount(5000)).toBe('5K')
  expect(formatCount(1_240_000)).toBe('1.2M')

  expect(progressBar(40, 200)).toEqual({ filled: '███', empty: '░'.repeat(13), percent: 20 })
  expect(progressBar(0, 0).percent).toBe(0)

  const all = TIPS.map(tip => tip.id)
  expect(nextTip([]).shown).toEqual([all[0]])
  expect(nextTip(all).shown).toEqual([all[0]])

  const install = INSTALL_TIPS.map(tip => tip.id)
  expect(nextTip([], INSTALL_TIPS).shown).toEqual([install[0]])
  expect(nextTip(install, INSTALL_TIPS).tip).toBe(INSTALL_TIPS[0]?.text)
})
