// Wraps a species name into multiple lines for Chart.js axis tick labels.
// Returns a plain string when it fits on one line, or an array of lines
// (Chart.js renders array tick labels as stacked lines).
export function wrapSpeciesLabel(name, maxChars = 14) {
  const words = name.split(' ')
  const lines = []
  let current = ''
  for (const word of words) {
    const candidate = current ? current + ' ' + word : word
    if (candidate.length > maxChars && current) {
      lines.push(current)
      current = word
    } else {
      current = candidate
    }
  }
  if (current) lines.push(current)
  return lines.length === 1 ? lines[0] : lines
}
