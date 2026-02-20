/**
 * Pong game — canvas-based implementation.
 *
 * Features:
 *  - Mode selection: 1-player vs AI or 2-player local
 *  - requestAnimationFrame game loop
 *  - Physics: ball velocity, wall + paddle bouncing, angle variation on hit position
 *  - Single-player AI: right paddle tracks ball Y with configurable speed cap
 *  - Two-player keyboard: left = W/S, right = Up/Down
 *  - Mobile two-player: left-side touch drag (left paddle), right-side touch drag (right paddle)
 *  - First to 7 points wins; rematch button
 *  - Pause on tab blur
 *  - devicePixelRatio canvas scaling for sharp Retina rendering
 */

;(function () {
  'use strict'

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  const CANVAS_W = 800 // logical CSS pixels
  const CANVAS_H = 480

  const PADDLE_W = 14
  const PADDLE_H = 80
  const PADDLE_MARGIN = 20 // distance from edge
  const BALL_SIZE = 12

  const BALL_SPEED_INIT = 5 // pixels per frame (at 60 fps)
  const BALL_SPEED_MAX = 14
  const BALL_SPEED_INCREMENT = 0.4 // per paddle hit

  const WIN_SCORE = 7

  // AI
  const AI_SPEED = 4.5 // max px/frame the AI paddle can move

  // Colours
  const COLOR_BG = '#1a1a1a'
  const COLOR_PADDLE = '#e0e0e0'
  const COLOR_BALL = '#f5c518'
  const COLOR_NET = '#444'
  const COLOR_TEXT = '#fff'
  const COLOR_SCORE = '#e0e0e0'

  // ---------------------------------------------------------------------------
  // DOM references
  // ---------------------------------------------------------------------------
  const modeScreen = /** @type {HTMLElement} */ (document.getElementById('pong-mode-screen'))
  const gameScreen = /** @type {HTMLElement} */ (document.getElementById('pong-game-screen'))
  const canvas = /** @type {HTMLCanvasElement} */ (document.getElementById('pong-canvas'))
  const ctx = /** @type {CanvasRenderingContext2D} */ (canvas.getContext('2d'))
  const btn1p = document.getElementById('btn-1p')
  const btn2p = document.getElementById('btn-2p')
  const modeLabel = /** @type {HTMLElement} */ (document.getElementById('mode-label'))

  // ---------------------------------------------------------------------------
  // Scale canvas for device pixel ratio
  // ---------------------------------------------------------------------------
  const DPR = window.devicePixelRatio || 1
  canvas.width = CANVAS_W * DPR
  canvas.height = CANVAS_H * DPR
  canvas.style.width = CANVAS_W + 'px'
  canvas.style.height = CANVAS_H + 'px'
  ctx.scale(DPR, DPR)

  // ---------------------------------------------------------------------------
  // Game state
  // ---------------------------------------------------------------------------
  /** @type {'idle'|'running'|'paused'|'over'} */
  let gameState = 'idle'
  /** @type {'1p'|'2p'} */
  let mode = '1p'

  let leftY = 0
  let rightY = 0
  let ballX = 0
  let ballY = 0
  let ballVX = 0
  let ballVY = 0
  let leftScore = 0
  let rightScore = 0
  let rafId = null

  // Keys held
  const keys = {}

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function clampPaddle(y) {
    return Math.max(0, Math.min(CANVAS_H - PADDLE_H, y))
  }

  function resetBall(direction) {
    ballX = CANVAS_W / 2
    ballY = CANVAS_H / 2
    const angle = (Math.random() * Math.PI) / 4 - Math.PI / 8 // ±22.5°
    ballVX = BALL_SPEED_INIT * direction * Math.cos(angle)
    ballVY = BALL_SPEED_INIT * Math.sin(angle)
  }

  function initGame() {
    leftY = (CANVAS_H - PADDLE_H) / 2
    rightY = (CANVAS_H - PADDLE_H) / 2
    leftScore = 0
    rightScore = 0
    updateScoreDisplay()
    resetBall(Math.random() < 0.5 ? 1 : -1)
  }

  function updateScoreDisplay() {
    const el = document.getElementById('pong-score')
    if (el) el.textContent = leftScore + '  —  ' + rightScore
  }

  // ---------------------------------------------------------------------------
  // AI paddle
  // ---------------------------------------------------------------------------
  function moveAI() {
    const center = rightY + PADDLE_H / 2
    const diff = ballY - center
    const move = Math.min(Math.abs(diff), AI_SPEED) * Math.sign(diff)
    rightY = clampPaddle(rightY + move)
  }

  // ---------------------------------------------------------------------------
  // Update
  // ---------------------------------------------------------------------------
  function update() {
    // Move left paddle (player always controls left)
    if (keys['w'] || keys['W']) leftY = clampPaddle(leftY - 6)
    if (keys['s'] || keys['S']) leftY = clampPaddle(leftY + 6)

    // Move right paddle
    if (mode === '2p') {
      if (keys['ArrowUp']) rightY = clampPaddle(rightY - 6)
      if (keys['ArrowDown']) rightY = clampPaddle(rightY + 6)
    } else {
      moveAI()
    }

    // Move ball
    ballX += ballVX
    ballY += ballVY

    // Top / bottom wall bounce
    if (ballY - BALL_SIZE / 2 <= 0) {
      ballY = BALL_SIZE / 2
      ballVY = Math.abs(ballVY)
    } else if (ballY + BALL_SIZE / 2 >= CANVAS_H) {
      ballY = CANVAS_H - BALL_SIZE / 2
      ballVY = -Math.abs(ballVY)
    }

    // Left paddle collision
    const leftPaddleRight = PADDLE_MARGIN + PADDLE_W
    if (
      ballX - BALL_SIZE / 2 <= leftPaddleRight &&
      ballX - BALL_SIZE / 2 >= PADDLE_MARGIN &&
      ballY >= leftY &&
      ballY <= leftY + PADDLE_H &&
      ballVX < 0
    ) {
      ballX = leftPaddleRight + BALL_SIZE / 2
      const hitPos = (ballY - (leftY + PADDLE_H / 2)) / (PADDLE_H / 2) // -1 to 1
      const speed = Math.min(Math.hypot(ballVX, ballVY) + BALL_SPEED_INCREMENT, BALL_SPEED_MAX)
      const angle = hitPos * (Math.PI / 3) // max 60°
      ballVX = speed * Math.cos(angle)
      ballVY = speed * Math.sin(angle)
    }

    // Right paddle collision
    const rightPaddleLeft = CANVAS_W - PADDLE_MARGIN - PADDLE_W
    if (
      ballX + BALL_SIZE / 2 >= rightPaddleLeft &&
      ballX + BALL_SIZE / 2 <= CANVAS_W - PADDLE_MARGIN &&
      ballY >= rightY &&
      ballY <= rightY + PADDLE_H &&
      ballVX > 0
    ) {
      ballX = rightPaddleLeft - BALL_SIZE / 2
      const hitPos = (ballY - (rightY + PADDLE_H / 2)) / (PADDLE_H / 2)
      const speed = Math.min(Math.hypot(ballVX, ballVY) + BALL_SPEED_INCREMENT, BALL_SPEED_MAX)
      const angle = hitPos * (Math.PI / 3)
      ballVX = -speed * Math.cos(angle)
      ballVY = speed * Math.sin(angle)
    }

    // Scoring — ball exits left
    if (ballX + BALL_SIZE / 2 < 0) {
      rightScore += 1
      updateScoreDisplay()
      if (rightScore >= WIN_SCORE) {
        endGame(mode === '1p' ? 'AI wins!' : 'Right player wins!')
        return
      }
      resetBall(1)
    }

    // Scoring — ball exits right
    if (ballX - BALL_SIZE / 2 > CANVAS_W) {
      leftScore += 1
      updateScoreDisplay()
      if (leftScore >= WIN_SCORE) {
        endGame(mode === '1p' ? 'You win!' : 'Left player wins!')
        return
      }
      resetBall(-1)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  function render() {
    // Background
    ctx.fillStyle = COLOR_BG
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)

    // Net (dashed centre line)
    ctx.strokeStyle = COLOR_NET
    ctx.lineWidth = 2
    ctx.setLineDash([12, 10])
    ctx.beginPath()
    ctx.moveTo(CANVAS_W / 2, 0)
    ctx.lineTo(CANVAS_W / 2, CANVAS_H)
    ctx.stroke()
    ctx.setLineDash([])

    // Left paddle
    ctx.fillStyle = COLOR_PADDLE
    ctx.fillRect(PADDLE_MARGIN, leftY, PADDLE_W, PADDLE_H)

    // Right paddle
    ctx.fillStyle = COLOR_PADDLE
    ctx.fillRect(CANVAS_W - PADDLE_MARGIN - PADDLE_W, rightY, PADDLE_W, PADDLE_H)

    // Ball
    ctx.fillStyle = COLOR_BALL
    ctx.beginPath()
    ctx.arc(ballX, ballY, BALL_SIZE / 2, 0, Math.PI * 2)
    ctx.fill()
  }

  // ---------------------------------------------------------------------------
  // Game loop
  // ---------------------------------------------------------------------------
  function loop() {
    if (gameState !== 'running') return
    update()
    if (gameState === 'running') {
      render()
      rafId = requestAnimationFrame(loop)
    }
  }

  function startGame(selectedMode) {
    mode = selectedMode
    modeScreen.style.display = 'none'
    gameScreen.style.display = 'flex'
    if (modeLabel) {
      modeLabel.textContent = mode === '1p' ? '1-Player vs AI' : '2-Player Local'
    }
    initGame()
    gameState = 'running'
    render()
    rafId = requestAnimationFrame(loop)
  }

  // ---------------------------------------------------------------------------
  // Game over
  // ---------------------------------------------------------------------------
  function endGame(message) {
    gameState = 'over'
    cancelAnimationFrame(rafId)

    // Overlay
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
    ctx.fillStyle = COLOR_TEXT
    ctx.font = 'bold 42px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(message, CANVAS_W / 2, CANVAS_H / 2 - 20)
    ctx.font = '22px sans-serif'
    ctx.fillText(leftScore + ' — ' + rightScore, CANVAS_W / 2, CANVAS_H / 2 + 20)
    ctx.font = '18px sans-serif'
    ctx.fillStyle = '#aaa'
    ctx.fillText('Press R or tap Rematch to play again', CANVAS_W / 2, CANVAS_H / 2 + 56)

    // Show rematch button
    const rematchBtn = document.getElementById('rematch-btn')
    if (rematchBtn) rematchBtn.style.display = 'inline-block'
  }

  // ---------------------------------------------------------------------------
  // Pause on tab blur
  // ---------------------------------------------------------------------------
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && gameState === 'running') {
      gameState = 'paused'
      cancelAnimationFrame(rafId)

      ctx.fillStyle = 'rgba(0,0,0,0.55)'
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
      ctx.fillStyle = COLOR_TEXT
      ctx.font = 'bold 36px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Paused', CANVAS_W / 2, CANVAS_H / 2)
    } else if (!document.hidden && gameState === 'paused') {
      gameState = 'running'
      rafId = requestAnimationFrame(loop)
    }
  })

  // ---------------------------------------------------------------------------
  // Input — keyboard
  // ---------------------------------------------------------------------------
  document.addEventListener('keydown', (e) => {
    keys[e.key] = true
    // Prevent page scroll on arrow keys
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
      e.preventDefault()
    }
    // Rematch shortcut
    if ((e.key === 'r' || e.key === 'R') && gameState === 'over') {
      rematch()
    }
  })

  document.addEventListener('keyup', (e) => {
    keys[e.key] = false
  })

  // ---------------------------------------------------------------------------
  // Input — mobile touch (two-thumb drag)
  // ---------------------------------------------------------------------------
  /** @type {Map<number, 'left'|'right'>} */
  const touchSide = new Map()

  canvas.addEventListener(
    'touchstart',
    (e) => {
      for (const t of e.changedTouches) {
        // Determine which half of the canvas the touch started on
        const rect = canvas.getBoundingClientRect()
        const relX = t.clientX - rect.left
        touchSide.set(t.identifier, relX < rect.width / 2 ? 'left' : 'right')
      }
      e.preventDefault()
    },
    { passive: false },
  )

  canvas.addEventListener(
    'touchmove',
    (e) => {
      for (const t of e.changedTouches) {
        const side = touchSide.get(t.identifier)
        if (!side) continue
        const rect = canvas.getBoundingClientRect()
        // Map clientY to canvas logical Y, then centre paddle on finger
        const scaleY = CANVAS_H / rect.height
        const logicalY = (t.clientY - rect.top) * scaleY
        const newY = clampPaddle(logicalY - PADDLE_H / 2)
        if (side === 'left') leftY = newY
        if (side === 'right') rightY = newY
      }
      e.preventDefault()
    },
    { passive: false },
  )

  canvas.addEventListener('touchend', (e) => {
    for (const t of e.changedTouches) {
      touchSide.delete(t.identifier)
    }
  })

  canvas.addEventListener('touchcancel', (e) => {
    for (const t of e.changedTouches) {
      touchSide.delete(t.identifier)
    }
  })

  // ---------------------------------------------------------------------------
  // Rematch
  // ---------------------------------------------------------------------------
  function rematch() {
    const rematchBtn = document.getElementById('rematch-btn')
    if (rematchBtn) rematchBtn.style.display = 'none'
    initGame()
    gameState = 'running'
    render()
    rafId = requestAnimationFrame(loop)
  }

  // ---------------------------------------------------------------------------
  // Mode selection buttons
  // ---------------------------------------------------------------------------
  if (btn1p) btn1p.addEventListener('click', () => startGame('1p'))
  if (btn2p) btn2p.addEventListener('click', () => startGame('2p'))

  const rematchBtn = document.getElementById('rematch-btn')
  if (rematchBtn) {
    rematchBtn.addEventListener('click', rematch)
    rematchBtn.style.display = 'none'
  }

  // Initial background render so canvas isn't blank while mode screen shows
  render()
})()
