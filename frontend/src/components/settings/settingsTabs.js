// The tabs of the settings page, in the order a sound travels through the station:
// where it is heard, what hears it, what identifies it, and who gets told.
// The `name` is both the URL segment (/settings/<name>) and the translation key
// under page.settings.tabs.
export const SETTINGS_TABS = [
  { name: 'station', icon: 'bi-geo-alt' },
  { name: 'recording', icon: 'bi-mic' },
  { name: 'detection', icon: 'bi-cpu' },
  { name: 'notifications', icon: 'bi-bell' },
]

export const DEFAULT_SETTINGS_TAB = SETTINGS_TABS[0].name

export function isSettingsTab(name) {
  return SETTINGS_TABS.some((tab) => tab.name === name)
}
