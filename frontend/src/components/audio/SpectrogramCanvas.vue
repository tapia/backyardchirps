<template>
  <div class="spectrogram-wrapper">
    <div v-if="loading" class="spectrogram-state">
      <div class="spinner-border spinner-border-sm"></div>
    </div>
    <div v-else-if="error" class="spectrogram-state spectrogram-state--error">
      <i class="bi bi-soundwave"></i>
    </div>
    <div
      v-else
      class="spectrogram-container"
      :class="{ 'spectrogram-container--seekable': seekable }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
    >
      <canvas ref="canvasEl" class="spectrogram-canvas"></canvas>
      <div ref="playheadEl" class="spectrogram-playhead"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { CHART_COLORS } from '../../chartColors.js'

const props = defineProps({
  audioUrl: { type: String, default: null },
  audioEl: { default: null },
  seekable: { type: Boolean, default: true },
})

const emit = defineEmits(['seek', 'seek-end'])

// A 1024-sample window resolves 216 bins below MAX_DISPLAY_HZ rather than 108,
// which is what makes the taller canvas show detail instead of stretched rows.
// The window covers 21 ms, still short against a bird syllable, and the hop
// stays at 256 so time resolution is untouched.
const FFT_SIZE = 1024
const HOP_SIZE = 256
// Frequency ceiling of the drawing. How many FFT bins that is depends on the
// sample rate, which is not the clip's: decodeAudioData resamples to the
// AudioContext rate, and that follows the output device (44.1 kHz on plenty of
// desktops, 48 kHz on most phones). Counting a fixed number of bins would make
// the visible range vary per machine, cutting the top off the taller-rate
// devices' worth of spectrum. Deriving the count pins the axis instead.
const MAX_DISPLAY_HZ = 10125

const canvasEl = ref(null)
const playheadEl = ref(null)
const loading = ref(false)
const error = ref(false)

let rafId = null

function tickPlayhead() {
  const audio = props.audioEl
  if (playheadEl.value && audio && isFinite(audio.duration) && audio.duration > 0) {
    playheadEl.value.style.left = `${(audio.currentTime / audio.duration) * 100}%`
  }
  rafId = requestAnimationFrame(tickPlayhead)
}

onMounted(() => {
  rafId = requestAnimationFrame(tickPlayhead)
})
onUnmounted(() => {
  cancelAnimationFrame(rafId)
})

// Tap or drag anywhere on the spectrogram to seek. Pointer events unify mouse
// and touch; setPointerCapture keeps the drag alive when the finger slides off
// the element, and `touch-action: none` (see styles) stops the page scrolling
// so a horizontal drag scrubs instead. `seek` moves the position (audio stays
// paused while dragging); `seek-end` fires on release to resume playback.
let scrubbing = false

function onPointerDown(event) {
  if (!props.seekable) return
  event.currentTarget.setPointerCapture(event.pointerId)
  scrubbing = true
  emit('seek', seekFraction(event))
}

function onPointerMove(event) {
  if (!scrubbing) return
  emit('seek', seekFraction(event))
}

function onPointerUp() {
  if (!scrubbing) return
  scrubbing = false
  emit('seek-end')
}

function onPointerCancel() {
  scrubbing = false
}

function seekFraction(event) {
  const rect = event.currentTarget.getBoundingClientRect()
  const fraction = (event.clientX - rect.left) / rect.width
  return Math.min(1, Math.max(0, fraction))
}

watch(() => props.audioUrl, buildSpectrogram, { immediate: true })

async function buildSpectrogram(url) {
  if (!url) {
    loading.value = false
    error.value = false
    return
  }
  loading.value = true
  error.value = false

  try {
    const response = await fetch(url)
    const arrayBuffer = await response.arrayBuffer()
    const audioContext = new AudioContext()
    let audioBuffer
    try {
      audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
    } finally {
      await audioContext.close()
    }

    const samples = audioBuffer.getChannelData(0)
    const displayBins = countDisplayBins(audioBuffer.sampleRate)
    const hannWindow = buildHannWindow(FFT_SIZE)
    const numFrames = Math.max(1, Math.floor((samples.length - FFT_SIZE) / HOP_SIZE) + 1)
    const magnitudeFrames = computeMagnitudeFrames(samples, hannWindow, numFrames, displayBins)
    const imageData = renderToImageData(magnitudeFrames, numFrames, displayBins)

    loading.value = false
    await nextTick()

    const canvas = canvasEl.value
    if (!canvas) return
    canvas.width = numFrames
    canvas.height = displayBins
    canvas.getContext('2d').putImageData(imageData, 0, 0)
  } catch {
    error.value = true
    loading.value = false
  }
}

// Bins spanning 0 to MAX_DISPLAY_HZ, capped at the Nyquist limit so a low-rate
// context draws everything it has rather than reading past the end of the FFT.
function countDisplayBins(sampleRate) {
  const binWidthHz = sampleRate / FFT_SIZE
  return Math.min(FFT_SIZE / 2, Math.round(MAX_DISPLAY_HZ / binWidthHz))
}

function buildHannWindow(size) {
  const window = new Float32Array(size)
  for (let index = 0; index < size; index++) {
    window[index] = 0.5 * (1 - Math.cos((2 * Math.PI * index) / (size - 1)))
  }
  return window
}

function computeMagnitudeFrames(samples, hannWindow, numFrames, displayBins) {
  const magnitudeFrames = []
  const realPart = new Float32Array(FFT_SIZE)
  const imagPart = new Float32Array(FFT_SIZE)

  for (let frameIndex = 0; frameIndex < numFrames; frameIndex++) {
    const offset = frameIndex * HOP_SIZE
    realPart.fill(0)
    imagPart.fill(0)
    for (let sampleIndex = 0; sampleIndex < FFT_SIZE; sampleIndex++) {
      const sampleValue = offset + sampleIndex < samples.length ? samples[offset + sampleIndex] : 0
      realPart[sampleIndex] = sampleValue * hannWindow[sampleIndex]
    }
    applyFFT(realPart, imagPart)

    const frameMagnitudes = new Float32Array(displayBins)
    for (let binIndex = 0; binIndex < displayBins; binIndex++) {
      const magnitude = Math.sqrt(
        realPart[binIndex] * realPart[binIndex] + imagPart[binIndex] * imagPart[binIndex],
      )
      frameMagnitudes[binIndex] = 20 * Math.log10(Math.max(magnitude, 1e-10))
    }
    magnitudeFrames.push(frameMagnitudes)
  }
  return magnitudeFrames
}

function renderToImageData(magnitudeFrames, numFrames, displayBins) {
  let dbMin = Infinity
  let dbMax = -Infinity
  for (const frame of magnitudeFrames) {
    for (let binIndex = 0; binIndex < displayBins; binIndex++) {
      if (frame[binIndex] < dbMin) dbMin = frame[binIndex]
      if (frame[binIndex] > dbMax) dbMax = frame[binIndex]
    }
  }
  const dbRange = dbMax - dbMin || 1
  const { stops } = CHART_COLORS.spectrogram

  const imageData = new ImageData(numFrames, displayBins)
  for (let frameIndex = 0; frameIndex < numFrames; frameIndex++) {
    for (let binIndex = 0; binIndex < displayBins; binIndex++) {
      const normalizedDb = (magnitudeFrames[frameIndex][binIndex] - dbMin) / dbRange
      const [red, green, blue] = interpolateColor(normalizedDb, stops)
      const pixelX = frameIndex
      const pixelY = displayBins - 1 - binIndex
      const pixelIndex = (pixelY * numFrames + pixelX) * 4
      imageData.data[pixelIndex] = red
      imageData.data[pixelIndex + 1] = green
      imageData.data[pixelIndex + 2] = blue
      imageData.data[pixelIndex + 3] = 255
    }
  }
  return imageData
}

function interpolateColor(value, stops) {
  let lowerStop = stops[0]
  let upperStop = stops[stops.length - 1]
  for (let stopIndex = 0; stopIndex < stops.length - 1; stopIndex++) {
    if (value >= stops[stopIndex][0] && value <= stops[stopIndex + 1][0]) {
      lowerStop = stops[stopIndex]
      upperStop = stops[stopIndex + 1]
      break
    }
  }
  const range = upperStop[0] - lowerStop[0]
  const t = range === 0 ? 0 : (value - lowerStop[0]) / range
  return [
    Math.round(lowerStop[1][0] + t * (upperStop[1][0] - lowerStop[1][0])),
    Math.round(lowerStop[1][1] + t * (upperStop[1][1] - lowerStop[1][1])),
    Math.round(lowerStop[1][2] + t * (upperStop[1][2] - lowerStop[1][2])),
  ]
}

function applyFFT(realPart, imagPart) {
  const n = realPart.length
  let bitReversalJ = 0
  for (let index = 1; index < n; index++) {
    let bit = n >> 1
    while (bitReversalJ & bit) {
      bitReversalJ ^= bit
      bit >>= 1
    }
    bitReversalJ ^= bit
    if (index < bitReversalJ) {
      let temp = realPart[index]
      realPart[index] = realPart[bitReversalJ]
      realPart[bitReversalJ] = temp
      temp = imagPart[index]
      imagPart[index] = imagPart[bitReversalJ]
      imagPart[bitReversalJ] = temp
    }
  }
  for (let length = 2; length <= n; length <<= 1) {
    const angle = (-2 * Math.PI) / length
    const cosAngle = Math.cos(angle)
    const sinAngle = Math.sin(angle)
    const halfLength = length >> 1
    for (let i = 0; i < n; i += length) {
      let twiddleRe = 1
      let twiddleIm = 0
      for (let k = 0; k < halfLength; k++) {
        const upperRe =
          realPart[i + k + halfLength] * twiddleRe - imagPart[i + k + halfLength] * twiddleIm
        const upperIm =
          realPart[i + k + halfLength] * twiddleIm + imagPart[i + k + halfLength] * twiddleRe
        const lowerRe = realPart[i + k]
        const lowerIm = imagPart[i + k]
        realPart[i + k] = lowerRe + upperRe
        imagPart[i + k] = lowerIm + upperIm
        realPart[i + k + halfLength] = lowerRe - upperRe
        imagPart[i + k + halfLength] = lowerIm - upperIm
        const newTwiddleRe = twiddleRe * cosAngle - twiddleIm * sinAngle
        twiddleIm = twiddleRe * sinAngle + twiddleIm * cosAngle
        twiddleRe = newTwiddleRe
      }
    }
  }
}
</script>

<style scoped>
/* Fills whatever width the player gives it. The cap that keeps the drawing one
   shape at every viewport lives on the player root, so the transport controls
   line up with the drawing instead of running the full width of the card. */
.spectrogram-wrapper {
  width: 100%;
  border-radius: 0;
  overflow: hidden;
  background: var(--spectrogram-dark);
}

/* Same box as the canvas, so swapping in the drawing doesn't shift the page. */
.spectrogram-state {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: var(--spectrogram-ratio, 3);
  color: var(--warm-muted);
}

.spectrogram-state--error {
  font-size: 1.2rem;
  opacity: 0.4;
}

.spectrogram-container {
  position: relative;
  line-height: 0;
}

.spectrogram-container--seekable {
  cursor: pointer;
  /* Let horizontal drags scrub instead of scrolling the page on touch. */
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}

.spectrogram-canvas {
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: var(--spectrogram-ratio, 3);
}

.spectrogram-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: rgba(255, 255, 255, 0.85);
  transform: translateX(-50%);
  pointer-events: none;
}
</style>
