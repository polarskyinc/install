export type PolarSkyStatus = {
  folders: { scanned: number; sensitive: number; protected: number }
  controls: { active: number; recommended: number; critical_recommended: number }
}

export type Band = { status: PolarSkyStatus | null; tip: string }

declare module 'claude-code' {
  interface PluginState {
    'polar-sky-status': { band: Band | null }
  }
}
