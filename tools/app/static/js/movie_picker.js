/**
 * Movie Picker — client-side logic
 *
 * - Debounced TMDB search via /api/movies/search
 * - Keyboard-navigable dropdown
 * - Movie list management (add / remove)
 * - "Pick for me" button: random selection + detail fetch from /api/movies/{id}
 */

const searchInput = document.getElementById('movie-search')
const searchResults = document.getElementById('search-results')
const searchStatus = document.getElementById('search-status')
const movieList = document.getElementById('movie-list')
const emptyMsg = document.getElementById('empty-list-msg')
const pickBtn = document.getElementById('pick-btn')

const resultPlaceholder = document.getElementById('result-placeholder')
const resultCard = document.getElementById('result-card')
const resultPoster = document.getElementById('result-poster')
const resultTitle = document.getElementById('result-title')
const resultYear = document.getElementById('result-year')
const resultRuntime = document.getElementById('result-runtime')
const resultProviders = document.getElementById('result-providers')
const resultError = document.getElementById('result-error')

/** @type {Array<{id: number, title: string, year: string}>} */
const movies = []

let searchDebounce = null
let activeIndex = -1

// ── Search ────────────────────────────────────────────────────────────────────

searchInput.addEventListener('input', () => {
  clearTimeout(searchDebounce)
  const q = searchInput.value.trim()
  if (!q) {
    closeDropdown()
    return
  }
  searchStatus.textContent = 'Searching…'
  searchDebounce = setTimeout(() => fetchSearch(q), 300)
})

searchInput.addEventListener('keydown', (e) => {
  if (searchResults.classList.contains('hidden')) return
  const items = searchResults.querySelectorAll('li')
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex = Math.min(activeIndex + 1, items.length - 1)
    updateActive(items)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex = Math.max(activeIndex - 1, 0)
    updateActive(items)
  } else if (e.key === 'Enter' && activeIndex >= 0) {
    e.preventDefault()
    items[activeIndex]?.click()
  } else if (e.key === 'Escape') {
    closeDropdown()
  }
})

searchInput.addEventListener('blur', () => {
  // Delay close so clicks on results register first
  setTimeout(closeDropdown, 150)
})

function updateActive(items) {
  items.forEach((li, i) => li.setAttribute('aria-selected', String(i === activeIndex)))
}

async function fetchSearch(q) {
  try {
    const res = await fetch(`/api/movies/search?q=${encodeURIComponent(q)}`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      searchStatus.textContent = err.detail || 'Search failed.'
      closeDropdown()
      return
    }
    const data = await res.json()
    searchStatus.textContent = data.length ? '' : 'No results found.'
    renderDropdown(data)
  } catch {
    searchStatus.textContent = 'Network error. Please try again.'
    closeDropdown()
  }
}

function renderDropdown(results) {
  searchResults.innerHTML = ''
  activeIndex = -1
  if (!results.length) {
    closeDropdown()
    return
  }
  results.forEach((movie) => {
    const li = document.createElement('li')
    li.setAttribute('role', 'option')
    li.setAttribute('aria-selected', 'false')

    if (movie.poster_path) {
      const img = document.createElement('img')
      img.src = movie.poster_path
      img.alt = ''
      img.className = 'movie-thumb'
      li.appendChild(img)
    } else {
      const ph = document.createElement('div')
      ph.className = 'movie-thumb-placeholder'
      ph.textContent = '🎬'
      li.appendChild(ph)
    }

    const info = document.createElement('div')
    info.className = 'movie-info'
    const titleEl = document.createElement('span')
    titleEl.className = 'movie-title'
    titleEl.textContent = movie.title
    const yearEl = document.createElement('span')
    yearEl.className = 'movie-year'
    yearEl.textContent = movie.year !== 'N/A' ? movie.year : ''
    info.appendChild(titleEl)
    info.appendChild(yearEl)
    li.appendChild(info)

    li.addEventListener('click', () => addMovie(movie))
    searchResults.appendChild(li)
  })

  searchResults.classList.remove('hidden')
  searchInput.setAttribute('aria-expanded', 'true')
}

function closeDropdown() {
  searchResults.classList.add('hidden')
  searchInput.setAttribute('aria-expanded', 'false')
  activeIndex = -1
}

// ── Movie list ────────────────────────────────────────────────────────────────

function addMovie(movie) {
  if (movies.some((m) => m.id === movie.id)) {
    closeDropdown()
    searchInput.value = ''
    searchStatus.textContent = `"${movie.title}" is already in your list.`
    return
  }

  movies.push({ id: movie.id, title: movie.title, year: movie.year })
  renderMovieList()
  closeDropdown()
  searchInput.value = ''
  searchStatus.textContent = ''
}

function removeMovie(id) {
  const idx = movies.findIndex((m) => m.id === id)
  if (idx !== -1) movies.splice(idx, 1)
  renderMovieList()
}

function renderMovieList() {
  // Remove all items except the hidden empty-msg template (we re-use it)
  Array.from(movieList.querySelectorAll('li:not(#empty-list-msg)')).forEach((li) =>
    li.remove(),
  )

  if (movies.length === 0) {
    emptyMsg.classList.remove('hidden')
    pickBtn.disabled = true
    return
  }

  emptyMsg.classList.add('hidden')
  pickBtn.disabled = false

  movies.forEach((movie) => {
    const li = document.createElement('li')

    const nameEl = document.createElement('span')
    nameEl.className = 'movie-name'
    nameEl.textContent = `${movie.title}${movie.year !== 'N/A' && movie.year ? ` (${movie.year})` : ''}`

    const removeBtn = document.createElement('button')
    removeBtn.className = 'remove-btn'
    removeBtn.textContent = '✕'
    removeBtn.setAttribute('aria-label', `Remove ${movie.title}`)
    removeBtn.addEventListener('click', () => removeMovie(movie.id))

    li.appendChild(nameEl)
    li.appendChild(removeBtn)
    movieList.appendChild(li)
  })
}

// ── Pick ──────────────────────────────────────────────────────────────────────

pickBtn.addEventListener('click', async () => {
  if (!movies.length) return

  // Pick random movie
  const picked = movies[Math.floor(Math.random() * movies.length)]

  showLoading()

  try {
    const res = await fetch(`/api/movies/${picked.id}`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      showError(err.detail || 'Failed to fetch movie details.')
      return
    }
    const details = await res.json()
    showResult(details)
  } catch {
    showError('Network error. Please check your connection and try again.')
  }
})

function showLoading() {
  resultPlaceholder.classList.add('hidden')
  resultCard.classList.add('hidden')
  resultError.classList.add('hidden')

  resultPlaceholder.classList.remove('hidden')
  resultPlaceholder.innerHTML =
    '<span class="spinner"></span><p>Picking your movie…</p>'
}

function showError(message) {
  resultPlaceholder.classList.add('hidden')
  resultCard.classList.add('hidden')
  resultError.textContent = message
  resultError.classList.remove('hidden')
}

function formatRuntime(minutes) {
  if (!minutes) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

function showResult(details) {
  resultPlaceholder.classList.add('hidden')
  resultError.classList.add('hidden')

  // Poster
  if (details.poster_url) {
    resultPoster.src = details.poster_url
    resultPoster.alt = details.title
    resultPoster.classList.remove('hidden')
    resultPoster.classList.remove('result-poster-placeholder')
    resultPoster.className = 'result-poster'
  } else {
    resultPoster.src = ''
    resultPoster.alt = 'No poster available'
    resultPoster.className = 'result-poster-placeholder'
    resultPoster.textContent = '🎬'
  }

  resultTitle.textContent = details.title
  resultYear.textContent = details.year !== 'N/A' ? details.year : ''

  const runtime = formatRuntime(details.runtime)
  resultRuntime.textContent = runtime ? `⏱ ${runtime}` : ''

  // Providers
  resultProviders.innerHTML = ''
  const hasStreaming = details.streaming.length > 0
  const hasRent = details.rent.length > 0
  const hasBuy = details.buy.length > 0

  if (!hasStreaming && !hasRent && !hasBuy) {
    const p = document.createElement('p')
    p.className = 'no-providers'
    p.textContent = 'No US streaming or rental info available.'
    resultProviders.appendChild(p)
  } else {
    if (hasStreaming) renderProviderGroup('Stream', details.streaming)
    if (hasRent) renderProviderGroup('Rent', details.rent)
    if (hasBuy) renderProviderGroup('Buy', details.buy)
  }

  resultCard.classList.remove('hidden')
}

function renderProviderGroup(label, providers) {
  const h4 = document.createElement('h4')
  h4.textContent = label
  resultProviders.appendChild(h4)

  const logos = document.createElement('div')
  logos.className = 'provider-logos'

  providers.forEach((p) => {
    if (p.logo_url) {
      const img = document.createElement('img')
      img.src = p.logo_url
      img.alt = p.provider_name
      img.title = p.provider_name
      img.className = 'provider-logo'
      logos.appendChild(img)
    } else {
      const span = document.createElement('span')
      span.textContent = p.provider_name
      span.className = 'result-meta'
      logos.appendChild(span)
    }
  })

  resultProviders.appendChild(logos)
}
