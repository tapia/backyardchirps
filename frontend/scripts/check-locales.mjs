// Compile every translated string the way vue-i18n does at runtime, and fail on any it
// refuses.
//
// This exists because a bad string is invisible to everything else. ESLint, Prettier and
// the build all see a valid JavaScript file, and vue-i18n only compiles a message when
// something renders it. A message that throws takes down the component rendering it, so
// the symptom is a piece of the page silently missing, on a station, with nothing failing
// anywhere a developer looks.
//
// The case that got us: 'From @BotFather.' A bare @ starts a linked message (@:some.key),
// so the compiler threw and the whole Keys and tokens card stopped rendering. Write a
// literal one as {'@'}.

import { baseCompile } from '@intlify/message-compiler'

import en from '../src/locales/en.js'
import es from '../src/locales/es.js'

const LOCALES = { en, es }

function* strings(value, path) {
  if (typeof value === 'string') {
    yield [path, value]
    return
  }
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      yield* strings(child, path ? `${path}.${key}` : key)
    }
  }
}

const failures = []
let checked = 0

for (const [locale, messages] of Object.entries(LOCALES)) {
  for (const [path, message] of strings(messages, '')) {
    checked += 1
    try {
      baseCompile(message, {
        onError(error) {
          throw error
        },
      })
    } catch (error) {
      failures.push({ locale, path, message, reason: error.message })
    }
  }
}

if (failures.length) {
  console.error(`${failures.length} of ${checked} messages will not compile:\n`)
  for (const { locale, path, message, reason } of failures) {
    console.error(`  ${locale}.${path}`)
    console.error(`    ${reason}`)
    console.error(`    ${message}\n`)
  }
  console.error("A literal @ is written {'@'}, and a literal brace {'{'}.")
  process.exit(1)
}

console.log(`${checked} messages compile.`)
