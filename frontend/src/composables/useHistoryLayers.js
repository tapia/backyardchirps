import { onUnmounted } from 'vue'

// A stack of dismissible UI layers backed by browser history, so the OS Back button
// closes the topmost layer instead of navigating the underlying route away.
//
// Each open layer pushes one history entry and remembers how to tear itself down.
// Back pops the top entry and dismisses that layer; the layers below it stay open.
//
// A layer can be dismissed from the app instead (a Cancel button, picking a species).
// That is `pop()`, which drops the entry the layer owns without letting the popstate
// handler run, so the two routes leave the stack in the same state.
export function useHistoryLayers() {
  // One dismiss callback per pushed history entry, topmost last.
  const dismissCallbacks = []
  // history.back() is asynchronous, so a programmatic pop is counted here and the
  // popstate it causes is skipped rather than treated as the user pressing Back.
  let popsToIgnore = 0
  let listening = false

  function onPopState() {
    if (popsToIgnore > 0) {
      popsToIgnore -= 1
      return
    }
    // The browser has already consumed the entry, so drop it before dismissing.
    // That is what lets a layer's own dismissal call close() without trying to
    // unwind an entry that is gone.
    const dismiss = dismissCallbacks.pop()
    dismiss?.()
  }

  function start() {
    if (listening) return
    window.addEventListener('popstate', onPopState)
    listening = true
  }

  function stop() {
    if (!listening) return
    window.removeEventListener('popstate', onPopState)
    listening = false
  }

  function push(dismiss) {
    dismissCallbacks.push(dismiss)
    history.pushState({ historyLayer: true }, '')
  }

  // Dismiss the top layer from the app. The caller has already torn the layer down,
  // so this only gives back the history entry it was holding.
  function pop() {
    if (!dismissCallbacks.length) return
    dismissCallbacks.pop()
    popsToIgnore += 1
    history.back()
  }

  // Give back every entry still held. A no-op when Back is what got us here, since
  // the browser consumed that entry and onPopState dropped its callback.
  function clear() {
    let remaining = dismissCallbacks.length
    dismissCallbacks.length = 0
    while (remaining-- > 0) history.back()
  }

  function depth() {
    return dismissCallbacks.length
  }

  onUnmounted(stop)

  return { start, stop, push, pop, clear, depth }
}
