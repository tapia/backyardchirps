// Shared vue-router location builders, so every component links to a given
// destination the same way. Species are always identified by their slug.
export function speciesRoute(speciesSlug) {
  return {
    name: 'species-detail',
    params: { slug: speciesSlug },
  }
}

// The clip (recording) detail page for a detection id.
export function recordingRoute(detectionId) {
  return {
    name: 'recording-detail',
    params: { id: detectionId },
  }
}
