<template>
  <footer class="site-footer">
    <div class="container">
      <p class="footer-intro">{{ t('footer.intro') }}</p>

      <ul class="footer-credits">
        <li v-for="credit in credits" :key="credit.url" class="footer-credit">
          <a
            :href="credit.url"
            target="_blank"
            rel="noopener noreferrer"
            class="footer-credit-link"
          >
            <img
              v-if="credit.logo"
              :src="credit.logo"
              alt=""
              class="footer-logo"
              @error="hideBrokenLogo"
            />
            <span class="footer-name">{{ credit.name }}</span>
          </a>
          <span class="footer-role">{{ t(credit.roleKey) }}</span>
        </li>
      </ul>

      <p class="footer-note">
        {{ t('footer.birdnetLicence') }}
        <a
          href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
          target="_blank"
          rel="noopener noreferrer"
          class="footer-link"
        >
          CC BY-NC-SA 4.0
        </a>
      </p>
    </div>
  </footer>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Data and service providers the station depends on. Each entry links to the
// source; the role is translated, the name never is. A credit without a logo
// falls back to its name as text, so a missing file degrades rather than
// leaving a gap in the row.
const credits = [
  {
    name: 'BirdNET',
    url: 'https://birdnet.cornell.edu',
    logo: '/icons/birdnet.png',
    roleKey: 'footer.roles.birdnet',
  },
  {
    name: 'eBird Status & Trends',
    url: 'https://science.ebird.org/en/status-and-trends',
    logo: '/icons/ebird.png',
    roleKey: 'footer.roles.ebird',
  },
  {
    name: 'xeno-canto',
    url: 'https://xeno-canto.org',
    logo: '/icons/xeno-canto.png',
    roleKey: 'footer.roles.xenoCanto',
  },
  {
    name: 'Open-Meteo',
    url: 'https://open-meteo.com',
    logo: '/icons/open-meteo.png',
    roleKey: 'footer.roles.openMeteo',
  },
  {
    name: 'ipgeolocation.io',
    url: 'https://ipgeolocation.io',
    logo: '/icons/ipgeolocation.png',
    roleKey: 'footer.roles.ipgeolocation',
  },
]

// A logo file that fails to load leaves the alt text in place instead of a
// broken-image glyph.
function hideBrokenLogo(event) {
  event.target.style.display = 'none'
}
</script>

<style scoped>
.site-footer {
  margin-top: 3rem;
  padding: 1.75rem 0 2rem;
  border-top: 1px solid var(--limestone);
  background: var(--sheet);
  color: var(--slate);
  font-size: 0.72rem;
  line-height: 1.5;
}

.footer-intro {
  margin-bottom: 0.85rem;
  font-weight: 600;
  color: var(--graphite);
}

.footer-credits {
  display: flex;
  flex-wrap: wrap;
  gap: 1.1rem 2rem;
  margin: 0 0 1.1rem;
  padding: 0;
  list-style: none;
}

.footer-credit {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  max-width: 12rem;
}

.footer-credit-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-height: 24px;
  text-decoration: none;
  color: var(--slate);
  opacity: 0.8;
  transition: opacity 0.12s;
}

.footer-credit-link:hover {
  opacity: 1;
}

/* Marks vary between square icons and wordmarks, so they are matched on
   height and left to take whatever width that implies. */
.footer-logo {
  width: auto;
  max-width: 64px;
  height: 22px;
  object-fit: contain;
  flex-shrink: 0;
}

.footer-name {
  font-weight: 600;
  color: var(--graphite);
  font-size: 0.78rem;
}

.footer-role {
  color: var(--dust);
  font-size: 0.66rem;
  line-height: 1.35;
}

.footer-note {
  margin-bottom: 0;
  color: var(--dust);
  font-size: 0.66rem;
}

.footer-link {
  color: var(--slate);
  text-decoration: none;
  border-bottom: 1px solid var(--limestone);
  transition:
    color 0.12s,
    border-color 0.12s;
}

.footer-link:hover {
  color: var(--lichen);
  border-bottom-color: var(--lichen);
}
</style>
