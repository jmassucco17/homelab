export function insertThemeToggle(containerId = 'theme-toggle-container') {
  const container = document.getElementById(containerId)
  if (!container) {
    console.warn(`Theme toggle container "${containerId}" not found.`)
    return
  }

  // Clear existing content
  container.innerHTML = ''

  const toggleButton = document.createElement('button')
  toggleButton.id = 'theme-toggle'
  toggleButton.className = 'theme-toggle'
  toggleButton.setAttribute('aria-label', 'Toggle theme')
  container.appendChild(toggleButton)

  const storedTheme = document.cookie
    .split('; ')
    .find((row) => row.startsWith('theme='))
    ?.split('=')[1]
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches

  const setTheme = (theme) => {
    document.documentElement.setAttribute('data-theme', theme)
    document.cookie = `theme=${theme}; path=/; domain=.jamesmassucco.com; SameSite=Lax`
    toggleButton.textContent = theme === 'dark' ? '🌙' : '☀️'
  }

  if (storedTheme) {
    setTheme(storedTheme)
  } else {
    setTheme(prefersDark ? 'dark' : 'light')
  }

  toggleButton.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme')
    setTheme(current === 'dark' ? 'light' : 'dark')
  })
}
