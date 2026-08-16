<template>
  <div class="settings-card">
    <h6 class="settings-section-title">
      <i class="bi bi-box-seam me-2"></i>{{ t('page.settings.regionPack') }}
    </h6>

    <p class="settings-hint">{{ t('page.settings.regionPackHint') }}</p>

    <p v-if="loading" class="text-muted small mb-0">{{ t('common.loading') }}</p>

    <template v-else>
      <p v-if="installedName" class="pack-line mb-2">
        <i class="bi bi-check-circle me-1"></i>
        {{ t('page.settings.regionPackInstalled', { name: installedName }) }}
      </p>

      <p v-if="unavailable" class="text-muted small mb-0">
        {{ t('page.settings.regionPackUnavailable') }}
      </p>

      <p v-else-if="brokeWith" class="text-muted small mb-0">
        {{ t('page.settings.regionPackBroken', { status: brokeWith }) }}
      </p>

      <template v-else-if="offered && !brokeWith">
        <p v-if="!covers" class="pack-line pack-line--miss mb-2">
          {{ t('page.settings.regionPackMiss', { name: offered.name, distance: distanceKm }) }}
          <a :href="requestUrl" target="_blank" rel="noopener">{{
            t('page.settings.regionPackRequest')
          }}</a>
        </p>
        <p v-else-if="!isInstalled" class="pack-line mb-2">
          {{ t('page.settings.regionPackCovers', { name: offered.name }) }}
        </p>

        <div v-if="running" class="progress pack-progress mb-2">
          <div class="progress-bar" :style="{ width: percent }"></div>
        </div>

        <p v-if="failed" class="pack-line pack-line--miss mb-2">
          {{ t('page.settings.regionPackFailed') }}
        </p>

        <button
          v-if="!isInstalled || !covers"
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="running"
          @click="install"
        >
          {{ running ? t('page.settings.regionPackWorking') : downloadLabel }}
        </button>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  fetchRegionPack,
  fetchInstalledRegionPack,
  startRegionPackInstall,
  fetchRegionPackInstallProgress,
} from '../../api/index.js'

const props = defineProps({
  latitude: { type: [String, Number], default: '' },
  longitude: { type: [String, Number], default: '' },
})

const { t } = useI18n()

// Where somebody with no pack over them is sent, so a miss becomes a request for a pack
// that ought to exist rather than a disappointment nobody hears about.
const requestUrl =
  'https://github.com/tapia/backyardchirps-regional-packs/issues/new?template=new-pack.yml'

// A pack takes minutes, so this is often enough for a bar that moves and rare enough to
// cost the station nothing.
const POLL_MS = 2000

// The coordinate fields update on every keystroke, and resolving a pack is a request that
// leaves the station. Without this, typing a latitude would ask the packs index once per
// character.
const SETTLE_MS = 600

const loading = ref(true)
const unavailable = ref(false)
const brokeWith = ref(null)
const offered = ref(null)
const covers = ref(false)
const distanceKm = ref(null)
const installedId = ref(null)
const progress = ref(null)

let polling = null
let settling = null

const isInstalled = computed(() => Boolean(offered.value) && offered.value.id === installedId.value)
const installedName = computed(() => (isInstalled.value ? offered.value.name : installedId.value))
const running = computed(() => progress.value?.state === 'running')
const failed = computed(() => progress.value?.state === 'failed')
const percent = computed(() =>
  progress.value?.fraction === null || progress.value?.fraction === undefined
    ? '100%'
    : `${Math.round(progress.value.fraction * 100)}%`,
)
const downloadLabel = computed(() =>
  installedId.value ? t('page.settings.regionPackSwitch') : t('page.settings.regionPackDownload'),
)

async function load() {
  loading.value = true
  unavailable.value = false
  try {
    const installed = await fetchInstalledRegionPack()
    installedId.value = installed.id
    if (props.latitude === '' || props.longitude === '') {
      offered.value = null
      return
    }
    const choice = await fetchRegionPack(props.latitude, props.longitude)
    offered.value = choice.region_pack
    covers.value = choice.covers
    distanceKm.value = choice.distance_km
  } catch (error) {
    // 503 is the one failure the station can explain: it could not read the index. Every
    // other status means something else went wrong, and saying "could not be reached"
    // for all of them sends whoever is reading it to look at the wrong thing.
    unavailable.value = error?.response?.status === 503
    brokeWith.value = unavailable.value ? null : (error?.response?.status ?? 'network')
    console.error('Region pack lookup failed', error)
  } finally {
    loading.value = false
  }
}

function stopPolling() {
  if (polling !== null) {
    window.clearInterval(polling)
    polling = null
  }
}

async function poll() {
  try {
    progress.value = await fetchRegionPackInstallProgress()
  } catch {
    // One failed poll says nothing: the download is running on the station, not here.
    return
  }
  if (progress.value?.state && progress.value.state !== 'running') {
    stopPolling()
    if (progress.value.state === 'done') await load()
  }
}

async function install() {
  progress.value = { state: 'running', fraction: 0 }
  try {
    await startRegionPackInstall(offered.value.id)
  } catch (error) {
    // 409 means one was already running, which is not a failure: watch that one.
    if (error?.response?.status !== 409) {
      progress.value = { state: 'failed' }
      return
    }
  }
  stopPolling()
  polling = window.setInterval(poll, POLL_MS)
}

onMounted(async () => {
  await load()
  // An install started from another tab, or from the wizard, is still worth showing.
  await poll()
  if (running.value) polling = window.setInterval(poll, POLL_MS)
})

onBeforeUnmount(() => {
  stopPolling()
  window.clearTimeout(settling)
})

watch(
  () => [props.latitude, props.longitude],
  () => {
    window.clearTimeout(settling)
    settling = window.setTimeout(load, SETTLE_MS)
  },
)
</script>

<style scoped>
.pack-line {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.85);
}
.pack-line--miss {
  color: rgba(255, 255, 255, 0.6);
}
.settings-hint {
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 1rem;
}
.pack-progress {
  height: 0.5rem;
  background-color: rgba(255, 255, 255, 0.1);
}
</style>
