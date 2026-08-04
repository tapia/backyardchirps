import client from './client.js'

export async function searchTaxonomy(query, lang) {
  const { data } = await client.get('/api/taxonomy/search/', { params: { q: query, lang } })
  return data.species
}
