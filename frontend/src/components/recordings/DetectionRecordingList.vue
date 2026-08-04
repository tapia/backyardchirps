<template>
  <div class="stat-card-warm p-3">
    <div v-if="!items.length" class="text-warm-muted small mt-2">
      {{ t('modal.noRecordings') }}
    </div>

    <!-- Date sort: recordings grouped into collapsible day cards -->
    <div v-else-if="groupByDay" class="day-groups">
      <div v-for="group in dayGroups" :key="group.key" class="day-group">
        <button
          type="button"
          class="day-header"
          :class="{ 'day-header--open': !isDayCollapsed(group.key) }"
          @click="toggleDay(group.key)"
        >
          <span class="day-label">{{ group.label }}</span>
          <span class="day-count">{{ group.items.length }}</span>
          <i
            class="bi ms-auto day-chevron"
            :class="isDayCollapsed(group.key) ? 'bi-chevron-down' : 'bi-chevron-up'"
          ></i>
        </button>

        <div v-if="!isDayCollapsed(group.key)" class="day-rows">
          <InlineAudioRow
            v-for="item in group.items"
            :key="item.url"
            class="px-3 py-2"
            :url="item.url"
            :active="isActive(item.url)"
            seekable
            @activate="activate(item.url)"
            @deactivate="deactivate"
          >
            <template #default="{ playing, play }">
              <div class="d-flex align-items-center gap-3">
                <PlayButton small :playing="playing" @click.stop="play" />
                <DetectionRecordingRow
                  :recording="item"
                  :show-actions="validate"
                  show-share
                  @validate="emit('validate', $event)"
                />
              </div>
            </template>
          </InlineAudioRow>
        </div>
      </div>
    </div>

    <!-- Confidence sort: plain flat list (rows carry the full date) -->
    <div v-else class="rec-list">
      <InlineAudioRow
        v-for="item in items"
        :key="item.url"
        class="px-3 py-2"
        :url="item.url"
        :active="isActive(item.url)"
        seekable
        @activate="activate(item.url)"
        @deactivate="deactivate"
      >
        <template #default="{ playing, play }">
          <div class="d-flex align-items-center gap-3">
            <PlayButton small :playing="playing" @click.stop="play" />
            <DetectionRecordingRow
              :recording="item"
              :show-actions="validate"
              show-share
              full-date
              @validate="emit('validate', $event)"
            />
          </div>
        </template>
      </InlineAudioRow>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useInlinePlayer } from '../../composables/useInlinePlayer.js'
import { dayKey, formatDayHeading } from '../../dates.js'
import DetectionRecordingRow from './DetectionRecordingRow.vue'
import InlineAudioRow from './InlineAudioRow.vue'
import PlayButton from '../audio/PlayButton.vue'

// The device's own captured detections for a species, played inline and
// reviewable, grouped into collapsible per-day cards. Each row's content is a
// shared DetectionRecordingRow. Reference examples live in ReferenceCallList.
const props = defineProps({
  recordings: { type: Array, default: () => [] },
  validate: { type: Boolean, default: false },
  // Group into collapsible day cards (date sort). When false, a plain flat
  // list — used for confidence sort, where day grouping would fight the order.
  groupByDay: { type: Boolean, default: false },
})

const emit = defineEmits(['validate'])

const { t } = useI18n()
const { isActive, activate, deactivate, reset } = useInlinePlayer()

const items = computed(() =>
  props.recordings.map((recording) => ({ ...recording, url: recording.clip_url })),
)

// Group recordings into calendar days, preserving the order they arrive in (the
// API's chosen sort), so a day appears where its recordings first show up.
const dayGroups = computed(() => {
  const groups = []
  const groupByKey = new Map()
  for (const item of items.value) {
    const key = dayKey(item.recorded_at)
    let group = groupByKey.get(key)
    if (!group) {
      group = { key, label: formatDayHeading(item.recorded_at), items: [] }
      groupByKey.set(key, group)
      groups.push(group)
    }
    group.items.push(item)
  }
  return groups
})

const collapsedDays = ref(new Set())

function isDayCollapsed(key) {
  return collapsedDays.value.has(key)
}

function toggleDay(key) {
  const next = new Set(collapsedDays.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedDays.value = next
}

watch(items, reset)
defineExpose({ reset })
</script>

<style scoped>
.rec-list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--limestone);
  margin-top: 8px;
}

.day-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.day-group {
  background: var(--sheet);
  border: 1px solid var(--border-soft);
  border-left: 3px solid var(--forest);
  border-radius: 10px;
  overflow: hidden;
}
.day-header {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  background: var(--paper);
  border: none;
  cursor: pointer;
  transition: background 0.12s;
}
.day-header:hover {
  background: var(--lichen-pale);
}
.day-header--open {
  border-bottom: 1px solid var(--border-soft);
}
.day-label {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--graphite);
}
.day-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.6em;
  padding: 0.05em 0.5em;
  border-radius: 999px;
  background: var(--limestone);
  color: var(--slate);
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1.5;
}
.day-chevron {
  font-size: 0.8rem;
  color: var(--slate);
}
</style>
