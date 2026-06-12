/**
 * Smoke test: type constants from @/components/lottery/types
 *
 * Verifies GAME_FORMATS has expected keys, required fields, example separators,
 * fadeIn animation keys, and BLOCK_COLOR_CLASSES structure.
 */
import { describe, it, expect } from 'vitest'
import { GAME_FORMATS, fadeIn, BLOCK_COLOR_CLASSES } from '@/components/lottery/types'

describe('GAME_FORMATS constants', () => {
  it('contains expected game keys', () => {
    const expectedKeys = ['4x20', '5x36', '7x49', '6x45plus', '5x36plus', '5x2', 'keno2']
    for (const key of expectedKeys) {
      expect(GAME_FORMATS[key], `Missing game key: ${key}`).toBeDefined()
    }
  })

  it('every game format has all required fields', () => {
    const requiredFields = ['blocks', 'pick_b1', 'pick_b2', 'b1_range', 'b2_range', 'example'] as const
    for (const [key, fmt] of Object.entries(GAME_FORMATS)) {
      for (const field of requiredFields) {
        expect(fmt, `Game "${key}" missing field "${field}"`).toHaveProperty(field)
        expect(fmt[field], `Game "${key}" field "${field}" should not be empty`).not.toBe('')
      }
    }
  })

  it('pick_b1 and pick_b2 are numbers', () => {
    for (const [key, fmt] of Object.entries(GAME_FORMATS)) {
      expect(typeof fmt.pick_b1, `${key}.pick_b1 should be number`).toBe('number')
      expect(typeof fmt.pick_b2, `${key}.pick_b2 should be number`).toBe('number')
    }
  })

  it('example strings contain "||" separator', () => {
    for (const [key, fmt] of Object.entries(GAME_FORMATS)) {
      expect(fmt.example, `${key}.example should contain ||`).toContain('||')
    }
  })

  it('has at least 20 game formats defined', () => {
    expect(Object.keys(GAME_FORMATS).length).toBeGreaterThanOrEqual(20)
  })
})

describe('fadeIn animation', () => {
  it('has all required animation keys', () => {
    const requiredKeys = ['initial', 'animate', 'exit', 'transition'] as const
    for (const key of requiredKeys) {
      expect(fadeIn, `fadeIn missing key "${key}"`).toHaveProperty(key)
    }
  })

  it('initial state has opacity and y', () => {
    expect(fadeIn.initial).toHaveProperty('opacity')
    expect(fadeIn.initial).toHaveProperty('y')
  })

  it('animate state has opacity and y', () => {
    expect(fadeIn.animate).toHaveProperty('opacity')
    expect(fadeIn.animate).toHaveProperty('y')
  })

  it('transition has duration', () => {
    expect(fadeIn.transition).toHaveProperty('duration')
    expect(typeof fadeIn.transition.duration).toBe('number')
  })
})

describe('BLOCK_COLOR_CLASSES', () => {
  it('has "blue" and "emerald" keys', () => {
    expect(BLOCK_COLOR_CLASSES).toHaveProperty('blue')
    expect(BLOCK_COLOR_CLASSES).toHaveProperty('emerald')
  })

  it('each color has bg, border, text, badge sub-keys', () => {
    const subKeys = ['bg', 'border', 'text', 'badge'] as const
    for (const color of ['blue', 'emerald'] as const) {
      for (const sub of subKeys) {
        expect(
          BLOCK_COLOR_CLASSES[color],
          `BLOCK_COLOR_CLASSES.${color} missing "${sub}"`,
        ).toHaveProperty(sub)
      }
    }
  })

  it('each sub-key is a non-empty string', () => {
    for (const color of Object.values(BLOCK_COLOR_CLASSES)) {
      for (const [sub, val] of Object.entries(color)) {
        expect(typeof val, `${sub} should be string`).toBe('string')
        expect(val.length, `${sub} should not be empty`).toBeGreaterThan(0)
      }
    }
  })
})
