/**
 * Snake game — canvas-based implementation.
 *
 * Features:
 *  - requestAnimationFrame game loop with configurable tick interval
 *  - Grid-based movement, wall and self-collision detection
 *  - Food spawning and score tracking
 *  - Keyboard controls (arrow keys / WASD)
 *  - Touch swipe controls + on-screen buttons
 *  - Game-over screen with restart button
 *  - Speed increases as score grows
 *  - High-score persisted in localStorage
 *  - devicePixelRatio canvas scaling for sharp Retina rendering
 */

;(function () {
  'use strict'

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  const COLS = 20
  const ROWS = 20
  const CELL = 24 // logical px per cell (CSS pixels)
  const CANVAS_CSS_SIZE = CELL * COLS // 480 CSS px square

  const BASE_INTERVAL_MS = 150 // ms between ticks at score 0
  const MIN_INTERVAL_MS = 60 // fastest tick interval
  const SPEED_STEP = 5 // score points per speed increase
  const SPEED_DELTA = 10 // ms reduction per SPEED_STEP

  // Colours
  const COLOR_BG = '#1a1a1a'
  const COLOR_GRID = '#222'
  const COLOR_SNAKE_HEAD = '#4caf50'
  const COLOR_SNAKE_BODY = '#388e3c'
  const COLOR_FOOD = '#e53935'
  const COLOR_TEXT = '#fff'

  // ---------------------------------------------------------------------------
  // DOM references
  // ---------------------------------------------------------------------------
  const canvas = /** @type {HTMLCanvasElement} */ (document.getElementById('snake-canvas'))
  const ctx = /** @type {CanvasRenderingContext2D} */ (canvas.getContext('2d'))
  const scoreEl = document.getElementById('score')
  const highScoreEl = document.getElementById('high-score')
  const startOverlay = document.getElementById('start-overlay')
  const startBtn = document.getElementById('start-btn')

  // ---------------------------------------------------------------------------
  // Scale canvas for device pixel ratio
  // ---------------------------------------------------------------------------
  const DPR = window.devicePixelRatio || 1
  canvas.width = CANVAS_CSS_SIZE * DPR
  canvas.height = CANVAS_CSS_SIZE * DPR
  canvas.style.width = CANVAS_CSS_SIZE + 'px'
  canvas.style.height = CANVAS_CSS_SIZE + 'px'
  ctx.scale(DPR, DPR)

  // ---------------------------------------------------------------------------
  // High score
  // ---------------------------------------------------------------------------
  let highScore = parseInt(localStorage.getItem('snake-high-score') || '0', 10)
  highScoreEl.textContent = String(highScore)

  // ---------------------------------------------------------------------------
  // Game state
  // ---------------------------------------------------------------------------
  /** @type {'idle'|'running'|'over'} */
  let state = 'idle'
  let snake = [] // [{x, y}, …] — head is index 0
  let dir = { x: 1, y: 0 } // current direction
  let nextDir = { x: 1, y: 0 } // queued direction (applied at next tick)
  let food = { x: 0, y: 0 }
  let score = 0
  let lastTick = 0
  let rafId = null

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function randomInt(max) {
    return Math.floor(Math.random() * max)
  }

  function spawnFood() {
    const occupied = new Set(snake.map((s) => s.x + ',' + s.y))
    let pos
    do {
      pos = { x: randomInt(COLS), y: randomInt(ROWS) }
    } while (occupied.has(pos.x + ',' + pos.y))
    food = pos
  }

  function intervalMs() {
    const steps = Math.floor(score / SPEED_STEP)
    return Math.max(MIN_INTERVAL_MS, BASE_INTERVAL_MS - steps * SPEED_DELTA)
  }

  // ---------------------------------------------------------------------------
  // Initialise / reset
  // ---------------------------------------------------------------------------
  function initGame() {
    const midX = Math.floor(COLS / 2)
    const midY = Math.floor(ROWS / 2)
    snake = [
      { x: midX, y: midY },
      { x: midX - 1, y: midY },
      { x: midX - 2, y: midY },
    ]
    dir = { x: 1, y: 0 }
    nextDir = { x: 1, y: 0 }
    score = 0
    scoreEl.textContent = '0'
    spawnFood()
  }

  // ---------------------------------------------------------------------------
  // Tick (update)
  // ---------------------------------------------------------------------------
  function tick() {
    dir = nextDir

    const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y }

    // Wall collision
    if (head.x < 0 || head.x >= COLS || head.y < 0 || head.y >= ROWS) {
      endGame()
      return
    }

    // Self collision
    if (snake.some((s) => s.x === head.x && s.y === head.y)) {
      endGame()
      return
    }

    snake.unshift(head)

    if (head.x === food.x && head.y === food.y) {
      score += 1
      scoreEl.textContent = String(score)
      if (score > highScore) {
        highScore = score
        highScoreEl.textContent = String(highScore)
        localStorage.setItem('snake-high-score', String(highScore))
      }
      spawnFood()
    } else {
      snake.pop()
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  function render() {
    // Background
    ctx.fillStyle = COLOR_BG
    ctx.fillRect(0, 0, CANVAS_CSS_SIZE, CANVAS_CSS_SIZE)

    // Grid lines (subtle)
    ctx.strokeStyle = COLOR_GRID
    ctx.lineWidth = 0.5
    for (let c = 0; c <= COLS; c++) {
      ctx.beginPath()
      ctx.moveTo(c * CELL, 0)
      ctx.lineTo(c * CELL, ROWS * CELL)
      ctx.stroke()
    }
    for (let r = 0; r <= ROWS; r++) {
      ctx.beginPath()
      ctx.moveTo(0, r * CELL)
      ctx.lineTo(COLS * CELL, r * CELL)
      ctx.stroke()
    }

    // Food
    ctx.fillStyle = COLOR_FOOD
    ctx.beginPath()
    ctx.arc(
      food.x * CELL + CELL / 2,
      food.y * CELL + CELL / 2,
      CELL / 2 - 2,
      0,
      Math.PI * 2,
    )
    ctx.fill()

    // Snake
    snake.forEach((seg, i) => {
      ctx.fillStyle = i === 0 ? COLOR_SNAKE_HEAD : COLOR_SNAKE_BODY
      ctx.fillRect(seg.x * CELL + 1, seg.y * CELL + 1, CELL - 2, CELL - 2)
    })
  }

  // ---------------------------------------------------------------------------
  // Game over
  // ---------------------------------------------------------------------------
  function endGame() {
    state = 'over'
    cancelAnimationFrame(rafId)

    // Draw game-over overlay on canvas
    ctx.fillStyle = 'rgba(0,0,0,0.55)'
    ctx.fillRect(0, 0, CANVAS_CSS_SIZE, CANVAS_CSS_SIZE)
    ctx.fillStyle = COLOR_TEXT
    ctx.font = `bold ${CELL * 1.4}px sans-serif`
    ctx.textAlign = 'center'
    ctx.fillText('Game Over', CANVAS_CSS_SIZE / 2, CANVAS_CSS_SIZE / 2 - CELL)
    ctx.font = `${CELL * 0.9}px sans-serif`
    ctx.fillText(`Score: ${score}`, CANVAS_CSS_SIZE / 2, CANVAS_CSS_SIZE / 2 + CELL * 0.5)

    // Reuse start overlay for restart
    const h2 = startOverlay.querySelector('h2')
    const p = startOverlay.querySelector('p')
    if (h2) h2.textContent = 'Game Over'
    if (p) p.textContent = `Score: ${score}  |  Best: ${highScore}`
    startBtn.textContent = 'Play Again'
    startOverlay.style.display = 'flex'
  }

  // ---------------------------------------------------------------------------
  // Game loop
  // ---------------------------------------------------------------------------
  function loop(ts) {
    if (state !== 'running') return
    if (ts - lastTick >= intervalMs()) {
      lastTick = ts
      tick()
      render()
    }
    if (state === 'running') {
      rafId = requestAnimationFrame(loop)
    }
  }

  function startGame() {
    initGame()
    state = 'running'
    startOverlay.style.display = 'none'
    render()
    lastTick = performance.now()
    rafId = requestAnimationFrame(loop)
  }

  // ---------------------------------------------------------------------------
  // Input — keyboard
  // ---------------------------------------------------------------------------
  const KEY_MAP = {
    ArrowUp: { x: 0, y: -1 },
    ArrowDown: { x: 0, y: 1 },
    ArrowLeft: { x: -1, y: 0 },
    ArrowRight: { x: 1, y: 0 },
    w: { x: 0, y: -1 },
    s: { x: 0, y: 1 },
    a: { x: -1, y: 0 },
    d: { x: 1, y: 0 },
    W: { x: 0, y: -1 },
    S: { x: 0, y: 1 },
    A: { x: -1, y: 0 },
    D: { x: 1, y: 0 },
  }

  document.addEventListener('keydown', (e) => {
    const d = KEY_MAP[e.key]
    if (!d) return
    // Prevent reversing into self
    if (d.x === -dir.x && d.y === -dir.y) return
    nextDir = d
    // Prevent page scroll on arrow keys
    e.preventDefault()
  })

  // ---------------------------------------------------------------------------
  // Input — touch swipe
  // ---------------------------------------------------------------------------
  let touchStart = null

  canvas.addEventListener(
    'touchstart',
    (e) => {
      touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY }
      e.preventDefault()
    },
    { passive: false },
  )

  canvas.addEventListener(
    'touchend',
    (e) => {
      if (!touchStart) return
      const dx = e.changedTouches[0].clientX - touchStart.x
      const dy = e.changedTouches[0].clientY - touchStart.y
      touchStart = null
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return // tap, not swipe
      let d
      if (Math.abs(dx) > Math.abs(dy)) {
        d = dx > 0 ? { x: 1, y: 0 } : { x: -1, y: 0 }
      } else {
        d = dy > 0 ? { x: 0, y: 1 } : { x: 0, y: -1 }
      }
      if (d.x === -dir.x && d.y === -dir.y) return
      nextDir = d
      e.preventDefault()
    },
    { passive: false },
  )

  // ---------------------------------------------------------------------------
  // Input — on-screen buttons
  // ---------------------------------------------------------------------------
  const BTN_DIRS = {
    'btn-up': { x: 0, y: -1 },
    'btn-down': { x: 0, y: 1 },
    'btn-left': { x: -1, y: 0 },
    'btn-right': { x: 1, y: 0 },
  }

  Object.entries(BTN_DIRS).forEach(([id, d]) => {
    const btn = document.getElementById(id)
    if (!btn) return
    const apply = (e) => {
      e.preventDefault()
      if (d.x === -dir.x && d.y === -dir.y) return
      nextDir = d
    }
    btn.addEventListener('touchstart', apply, { passive: false })
    btn.addEventListener('mousedown', apply)
  })

  // ---------------------------------------------------------------------------
  // Start button
  // ---------------------------------------------------------------------------
  startBtn.addEventListener('click', startGame)

  // Initial render to show the empty board behind the overlay
  initGame()
  render()
})()
