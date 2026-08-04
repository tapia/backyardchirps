// Primary navigation destinations, shared by the desktop and mobile navbars.
// `subtitleKey` is only shown by the mobile card layout.
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
  },
]
