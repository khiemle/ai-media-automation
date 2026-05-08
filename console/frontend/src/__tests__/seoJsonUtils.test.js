import { describe, it, expect } from 'vitest'
import { parseSeoJson, extractSeoFromSeoJson } from '../pages/YouTubeVideosPage.jsx'

const VALID_SEO_JSON = {
  meta: { video_title_slug: 'bamboo-engawa-rain', channel: 'soundscapes', video_length_hours: 8 },
  titles: {
    recommended: 'Bamboo Forest Rain · Japanese Koto Music for Studying · 8 Hours',
    alternatives: ['Japanese Study Music · Bamboo Rain & Koto Ambience · 8 Hours'],
  },
  description: {
    full: 'Bamboo forest rain ambience with Japanese koto music — designed for studying.',
  },
  tags: {
    all: ['study music', 'bamboo forest', 'koto music'],
  },
}

describe('parseSeoJson', () => {
  it('parses valid SEO JSON text', () => {
    const result = parseSeoJson(JSON.stringify(VALID_SEO_JSON))
    expect(result).toEqual(VALID_SEO_JSON)
  })

  it('throws on invalid JSON syntax', () => {
    expect(() => parseSeoJson('not json')).toThrow(SyntaxError)
  })

  it('throws when titles.recommended and description.full are both absent', () => {
    const bad = { meta: { channel: 'soundscapes' } }
    expect(() => parseSeoJson(JSON.stringify(bad))).toThrow('Not a valid SEO JSON')
  })

  it('accepts JSON that has description.full even without titles.recommended', () => {
    const partial = { description: { full: 'Some description' } }
    expect(() => parseSeoJson(JSON.stringify(partial))).not.toThrow()
  })

  it('accepts JSON that has titles.recommended even without description.full', () => {
    const partial = { titles: { recommended: 'Some Title' } }
    expect(() => parseSeoJson(JSON.stringify(partial))).not.toThrow()
  })
})

describe('extractSeoFromSeoJson', () => {
  it('maps titles.recommended to seo_title', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.seo_title).toBe('Bamboo Forest Rain · Japanese Koto Music for Studying · 8 Hours')
  })

  it('maps description.full to seo_description', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.seo_description).toBe('Bamboo forest rain ambience with Japanese koto music — designed for studying.')
  })

  it('joins tags.all as comma-separated string into seo_tags', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.seo_tags).toBe('study music, bamboo forest, koto music')
  })

  it('maps meta.video_length_hours to target_duration_h', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.target_duration_h).toBe(8)
  })

  it('returns null for missing optional fields', () => {
    const minimal = { titles: { recommended: 'Some Title' } }
    const result = extractSeoFromSeoJson(minimal)
    expect(result.seo_description).toBeNull()
    expect(result.seo_tags).toBeNull()
    expect(result.target_duration_h).toBeNull()
  })
})
