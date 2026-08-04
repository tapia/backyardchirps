<template>
  <RouterLink
    v-if="card"
    :to="to"
    class="feed-card h-100 shadow-sm text-reset text-decoration-none"
    :class="{ flash: flash }"
    @mouseenter="$emit('mouseenter')"
    @mouseleave="$emit('mouseleave')"
  >
    <img
      :src="species.image_url"
      :alt="species.common_name"
      class="feed-card__img"
      @error="$event.target.style.display = 'none'"
    />
    <div class="feed-card__body">
      <div class="feed-card__names">
        <div class="bird-name">{{ species.common_name }}</div>
        <div class="scientific-name">{{ species.scientific_name }}</div>
      </div>
      <div class="feed-card__stats">
        <div class="feed-stat">
          <span class="feed-stat__value">{{ species.count_in_period?.toLocaleString() }}</span>
          <span class="feed-stat__label">{{ periodLabel }}</span>
        </div>
        <div v-if="showLastSeen" class="feed-stat feed-stat--end">
          <span class="feed-stat__value">
            <span class="time-prep">{{ t('common.timeAgoPrefix') }}</span
            >{{ shortRelativeTime(species.last_seen)
            }}<span class="time-prep">{{ t('common.timeAgoSuffix') }}</span>
          </span>
          <span class="feed-stat__label">{{ t('common.lastSeenFull') }}</span>
        </div>
      </div>
    </div>
  </RouterLink>

  <RouterLink
    v-else
    :to="to"
    class="recent-row d-flex align-items-center gap-2 px-3 py-2 text-reset text-decoration-none"
    :class="{ flash: flash }"
    @mouseenter="$emit('mouseenter')"
    @mouseleave="$emit('mouseleave')"
  >
    <img
      :src="species.image_url"
      :alt="species.common_name"
      class="recent-row__img flex-shrink-0 rounded"
      @error="$event.target.style.display = 'none'"
    />
    <div class="flex-grow-1 overflow-hidden">
      <span class="bird-name">{{ species.common_name }}</span>
      <span class="scientific-name d-block d-sm-inline ms-0 ms-sm-2">{{
        species.scientific_name
      }}</span>
    </div>
    <div class="flex-shrink-0 text-end row-meta">
      <div class="row-meta__count">
        {{
          t('common.countInPeriod', {
            n: species.count_in_period?.toLocaleString(),
            period: periodLabel,
          })
        }}
      </div>
      <div class="row-meta__time">
        {{ t('common.latestDetection', { time: shortRelativeTime(species.last_seen) }) }}
      </div>
    </div>
  </RouterLink>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { shortRelativeTime } from '../../dates.js'

const { t } = useI18n()
defineProps({
  species: Object,
  to: { type: [Object, String], required: true },
  flash: Boolean,
  card: { type: Boolean, default: false },
  periodLabel: { type: String, default: '24h' },
  showLastSeen: { type: Boolean, default: true },
})
defineEmits(['mouseenter', 'mouseleave'])
</script>

<style scoped>
.feed-card {
  background: var(--bs-card-bg);
  border: 1px solid var(--limestone);
  border-radius: 2px;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: background 0.12s;
}
.feed-card:hover {
  background: var(--lichen-pale);
}

.feed-card__img {
  width: 100%;
  height: 176px;
  object-fit: contain;
  display: block;
  flex-shrink: 0;
}

.feed-card__body {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.feed-card__names {
  flex: 1;
  margin-bottom: 10px;
}

.feed-card__stats {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-top: 8px;
  border-top: 1px solid var(--warm-border);
}

.feed-stat {
  display: flex;
  flex-direction: column;
}
.feed-stat--end {
  align-items: flex-end;
}
.feed-stat__value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--brown);
  line-height: 1.1;
}
.feed-stat__label {
  font-size: 0.58rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--warm-muted);
  margin-top: 2px;
  white-space: nowrap;
}
.time-prep {
  font-size: 0.72rem;
  font-weight: 400;
}

.row-meta {
  white-space: nowrap;
}
.row-meta__count {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--brown);
}
.row-meta__time {
  font-size: 0.75rem;
  color: var(--warm-muted);
  margin-top: 0.15em;
}

@keyframes flash-card {
  0% {
    background-color: rgba(var(--lichen-rgb), 0.18);
  }
  100% {
    background-color: var(--bs-card-bg);
  }
}
.feed-card.flash {
  animation: flash-card 1.2s ease-out;
}

.recent-row {
  cursor: pointer;
  border-bottom: 1px solid var(--warm-border);
  transition: background 0.1s;
}
.recent-row:hover {
  background: var(--warm-card);
}

.recent-row__img {
  width: 56px;
  height: 56px;
  object-fit: cover;
}

.bird-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--graphite);
}
.scientific-name {
  font-family: 'Newsreader', Georgia, serif;
  font-style: italic;
  font-size: 0.78rem;
  color: var(--slate);
}

@keyframes flash-detection {
  0% {
    background-color: rgba(var(--lichen-rgb), 0.14);
  }
  100% {
    background-color: transparent;
  }
}
.recent-row.flash {
  animation: flash-detection 1.2s ease-out;
}
</style>
