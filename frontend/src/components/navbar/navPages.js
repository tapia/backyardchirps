// Primary navigation destinations, shared by the desktop and mobile navbars.
// `subtitleKey` is only shown by the mobile card layout. `requiresAdmin` mirrors the
// route's own guard, so a page nobody else can open is not offered to them either.
export const NAV_PAGES = [
  {
    routeName: 'recent',
    to: '/',
    icon: 'bi-clock-history',
    labelKey: 'nav.recent',
    subtitleKey: 'nav.recentSubtitle',
  },
  {
    routeName: 'species',
    to: '/species',
    icon: 'bi-list-ul',
    labelKey: 'nav.allSpecies',
    subtitleKey: 'nav.allSpeciesSubtitle',
  },
  {
    routeName: 'pending',
    to: '/pending-review',
    icon: 'bi-exclamation-circle',
    labelKey: 'nav.pendingReview',
    subtitleKey: 'nav.pendingSubtitle',
    requiresAdmin: true,
  },
]

export function visibleNavPages(isStaff) {
  return NAV_PAGES.filter((page) => !page.requiresAdmin || isStaff)
}
