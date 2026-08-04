import { ref } from 'vue'
import { fetchDubiousCount } from '../api/index.js'

const pendingCount = ref(null)

async function refresh() {
  pendingCount.value = await fetchDubiousCount()
}

refresh()
setInterval(refresh, 10_000)

export function useDubiousCount() {
  return { pendingCount, refresh }
}
