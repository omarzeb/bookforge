'use client'
import { useEffect } from 'react'

// Apply theme before first render to avoid flash
export function ThemeInit() {
  useEffect(() => {
    const saved = localStorage.getItem('theme')
    document.documentElement.classList.toggle('dark', saved !== 'light')
  }, [])
  return null
}
