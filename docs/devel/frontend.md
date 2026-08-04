# Frontend

A Vue 3 single-page app (Vite, `<script setup>`, plain JavaScript) consuming the Django REST
API. Styling is Bootstrap 5 plus the "Observatory" design tokens in `src/style.css`; charts are
Chart.js.

## Layout

```
frontend/src/
├── main.js               App bootstrap: plugins, dayjs locale sync, global directives
├── App.vue               Shell: navbar + router view; provides `lang` to all pages
├── style.css             Design tokens (:root custom properties) + global styles
├── i18n.js               vue-i18n setup
├── locales/              en.js / es.js UI strings; both must define the same keys
├── api/                  ALL backend communication (see below)
├── router/               Routes + the admin guard (meta.requiresAdmin)
├── pages/                One component per route, named <Thing>Page.vue
├── components/           Reusable UI in feature subfolders (species, recordings, charts,
│                         audio, review, feed, navbar, settings, common). Nothing loose.
├── composables/          Shared reactive logic (use*.js)
├── directives/           v-bs-tooltip
├── chartColors.js        Data-viz colours that JS itself must read
├── dates.js              Shared date/time formatters
├── links.js              vue-router location builders (speciesRoute, …)
├── speciesHighlights.js  Derives the hero facts (regularity, peak hours, streak)
├── chartModeStorage.js   Remembers chart mode across visits
└── periodStorage.js      Remembers the selected period across visits
```

**pages/** owns route-level state (filters, navigation offsets) and data loading, then puts
components together. **components/** is everything reusable, from the smallest single-purpose
pieces (`audio/PlayButton`, `common/ConfidenceBadge`) to whole workflows
(`review/ValidationModal`), each in the folder it belongs to. **composables/** is shared reactive
logic. A `ref` at module level makes state app-wide, which is how `useAuth` and
`useConfidenceFilter` work without a store, and `createPolledResource` provides the polling
behind `useServerStatus` and `useWeather`.

## The API layer

**Every** HTTP call goes through `src/api/`. Components and composables import named functions
from `../api/index.js` and never touch axios. One module per backend area, matching the features
in `backyardchirps/features/`: `auth`, `species`, `detections`, `taxonomy`, `settings`,
`weather`, `serverStatus`.

Three conventions make the layer worth having:

- **Named for the data, not the URL.** `fetchDetectionsPerHourOfDay()`, not `getSpeciesHourly()`.
- **camelCase in, wire names out.** Callers pass `minConfidence`, and the module sends
  `min_confidence`.
- **Wrappers are removed.** `fetchSpeciesList()` returns the array itself, not
  `{ species: [...] }`, so callers never see the shape the API happens to use.

`client.js` owns the shared axios instance and CSRF handling. `auth.js` installs the token after
login or session restore.

## Reuse these

Check this list before writing a helper.

| Piece | Use for |
|---|---|
| `useAudioPlayer` | Any `<audio>` element: play/pause, progress, clip switching (`toggleUrl`) |
| `useSettingsForm` | A settings card: field values, per-field errors, save flow |
| `useMediaQuery` | Reactive `matchMedia`, for changing a component's *structure* between mobile and desktop, which CSS alone cannot do |
| `dates.js` | Timestamps: `formatDate`, `formatDateTime`, `formatTime`, `shortRelativeTime` |
| `SpeciesSearchPicker` | Debounced taxonomy search input plus result list |
| `SlidePanel` | A full-height sliding panel for one focused task, mostly on mobile. Takes `title`, emits `close` |
| `ConfirmDialog` | Confirming a destructive action. Never use the browser's `confirm()` |

## Conventions

**Colours** are defined once as CSS custom properties in `src/style.css`. Never write a hex or
`rgb()` value in a `.vue` file: use `var(--forest)` in styles, and `chartColors.js` only where JS
itself has to read the value (Chart.js configs, canvas drawing).

**Tooltips** go through the `v-bs-tooltip` directive in `src/directives/`, never the native
`title` attribute. Icon-only controls also need an `:aria-label`.

**Named UI states are classes.** If a visual change has a name ("active", "validated", "hidden"),
toggle a class with `:class`. Setting `element.style` directly is only for a value that really is
calculated as the app runs and has no meaningful name, such as a pixel position.

## Language

`App.vue` provides the current locale as `lang`. Pages `inject('lang')` and pass `lang.value` to
API calls, so the backend returns localised common names. Interface strings live in
`locales/en.js` and `locales/es.js`, which must always define the same keys.

## Two visual systems

The light **Observatory** theme (paper, limestone, lichen tokens) covers the public pages. A dark
**admin** theme (`--admin-*` and `--status-card-*` tokens) covers login, settings and server
status. A component that can appear in both has to work in both.
