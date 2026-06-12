'use client'

import { useSyncExternalStore } from 'react'

function getSnapshot(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function getServerSnapshot(): boolean {
  return false
}

function subscribe(callback: () => void): () => void {
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  mq.addEventListener('change', callback)
  return () => mq.removeEventListener('change', callback)
}

/**
 * Returns true if the user has enabled "prefers-reduced-motion" in their OS settings.
 * Use this to skip heavy framer-motion animations.
 * Uses useSyncExternalStore for zero-re-render updates.
 */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
