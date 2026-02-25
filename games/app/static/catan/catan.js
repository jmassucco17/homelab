/**
 * Catan lobby and game-page orchestration.
 *
 * Loaded as a JS module by both catan_lobby.html and catan_game.html.
 * Detects which page it is on by checking for a root element ID, then
 * bootstraps the appropriate subsystem.
 *
 * Lobby page (id="catan-lobby"):
 *   - Create room (POST /catan/rooms) → redirect to game page
 *   - Join room by code → redirect to game page
 *
 * Game page (id="catan-game-area"):
 *   - Parse room code + player name from URL query params
 *   - Initialise CatanBoardRenderer, CatanUI, and CatanWSClient
 *   - Wire up callbacks for all WebSocket messages
 *   - Handle board click-events and translate them to game actions
 */

'use strict'

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

// Propagate the cache-busting version query parameter to sub-module imports
// so that board.js, ui.js, and ws_client.js are also re-fetched when any
// Catan JS file changes.
const _v = new URL(import.meta.url).search

document.addEventListener('DOMContentLoaded', async () => {
  if (document.getElementById('catan-lobby')) {
    initLobby()
  } else if (document.getElementById('catan-game-area')) {
    const [{ CatanBoardRenderer }, { CatanUI }, { CatanWSClient }] = await Promise.all([
      import(`/static/catan/board.js${_v}`),
      import(`/static/catan/ui.js${_v}`),
      import(`/static/catan/ws_client.js${_v}`),
    ])
    initGame(CatanBoardRenderer, CatanUI, CatanWSClient)
  }
})

// ---------------------------------------------------------------------------
// Lobby
// ---------------------------------------------------------------------------

function initLobby() {
  const createBtn = document.getElementById('btn-create-room')
  const joinBtn = document.getElementById('join-room-btn')
  const joinCodeInput = document.getElementById('join-room-code')
  const nameInput = document.getElementById('player-name-input')
  const errorEl = document.getElementById('lobby-error')

  function getName() {
    return nameInput ? nameInput.value.trim() : ''
  }

  function showError(msg) {
    if (errorEl) {
      errorEl.textContent = msg
      errorEl.style.display = 'block'
    }
  }

  function hideError() {
    if (errorEl) errorEl.style.display = 'none'
  }

  if (nameInput) {
    nameInput.addEventListener('input', hideError)
  }

  if (createBtn) {
    createBtn.addEventListener('click', async () => {
      hideError()
      const name = getName()
      if (!name) {
        showError('Please enter your name first.')
        return
      }
      createBtn.disabled = true
      createBtn.textContent = '⏳ Creating…'
      try {
        const resp = await fetch('/catan/rooms', { method: 'POST' })
        if (!resp.ok) throw new Error('Server error')
        const data = await resp.json()
        const code = data.room_code
        window.location.href = `/catan/game?room=${code}&name=${encodeURIComponent(name)}`
      } catch {
        showError('Could not create room — please try again.')
        createBtn.disabled = false
        createBtn.textContent = '🆕 Create New Room'
      }
    })
  }

  if (joinBtn) {
    joinBtn.addEventListener('click', () => {
      hideError()
      const name = getName()
      const code = joinCodeInput ? joinCodeInput.value.trim().toUpperCase() : ''
      if (!name) {
        showError('Please enter your name first.')
        return
      }
      if (!code || code.length !== 4 || !/^[A-Z0-9]{4}$/.test(code)) {
        showError('Enter a valid 4-character room code.')
        return
      }
      window.location.href = `/catan/game?room=${code}&name=${encodeURIComponent(name)}`
    })
  }

  // Allow pressing Enter in the join-code field
  if (joinCodeInput) {
    joinCodeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') joinBtn && joinBtn.click()
    })
    // Force uppercase while typing
    joinCodeInput.addEventListener('input', () => {
      const start = joinCodeInput.selectionStart
      const end = joinCodeInput.selectionEnd
      joinCodeInput.value = joinCodeInput.value.toUpperCase()
      joinCodeInput.setSelectionRange(start, end)
    })
  }

  // Poll for active games and populate the active-games section
  loadActiveGames()
  const pollInterval = setInterval(loadActiveGames, 5000)
  window.addEventListener('beforeunload', () => clearInterval(pollInterval))
}

/** Fetch active rooms and render them in the active-games section. */
async function loadActiveGames() {
  const listEl = document.getElementById('active-games-list')
  const emptyEl = document.getElementById('active-games-empty')
  if (!listEl || !emptyEl) return

  try {
    const resp = await fetch('/catan/rooms')
    if (!resp.ok) return
    const rooms = await resp.json()

    listEl.innerHTML = ''

    if (rooms.length === 0) {
      emptyEl.style.display = 'block'
      return
    }

    emptyEl.style.display = 'none'
    rooms.forEach((room) => {
      const card = document.createElement('div')
      card.className = 'active-game-card'

      const playerNames = room.players.length > 0 ? room.players.join(', ') : 'No players yet'
      const phaseLabel = room.phase === 'lobby' ? 'In Lobby' : `In Game (${room.phase})`

      card.innerHTML = `
        <div class="active-game-info">
          <span class="active-game-code">${room.room_code}</span>
          <span class="active-game-phase">${phaseLabel}</span>
          <span class="active-game-players">👤 ${playerNames}</span>
        </div>
        <button class="lobby-btn observe-btn" data-room="${room.room_code}">👁 Observe</button>
      `
      listEl.appendChild(card)
    })

    // Wire up observe buttons
    listEl.querySelectorAll('.observe-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const code = btn.dataset.room
        window.location.href = `/catan/game?room=${code}&observe=true`
      })
    })
  } catch {
    // Silently ignore errors; the section will stay as-is
  }
}

// ---------------------------------------------------------------------------
// Game page
// ---------------------------------------------------------------------------

async function initGame(CatanBoardRenderer, CatanUI, CatanWSClient) {
  const params = new URLSearchParams(window.location.search)
  const roomCode = params.get('room')
  const playerName = params.get('name') || 'Player'
  const isObserver = params.get('observe') === 'true'

  if (!roomCode) {
    window.location.href = '/catan'
    return
  }

  // Show room code in waiting room header and rejoin prompt
  const rcEl = document.getElementById('room-code-display')
  if (rcEl) rcEl.textContent = roomCode
  const rejoinRoomCodeEl = document.getElementById('rejoin-room-code')
  if (rejoinRoomCodeEl) rejoinRoomCodeEl.textContent = roomCode

  // In observer mode, hide the waiting-room action buttons (can't start/add AI)
  if (isObserver) {
    const waitingActions = document.querySelector('.waiting-room-actions')
    if (waitingActions) waitingActions.style.display = 'none'
    const waitingHint = document.querySelector('.waiting-hint')
    if (waitingHint) waitingHint.textContent = 'You are observing this game.'
    // If game already started, skip straight to game view
    document.getElementById('waiting-room')?.classList.remove('hidden')
  }

  // ---------------------------------------------------------------------------
  // Board renderer
  // ---------------------------------------------------------------------------
  const canvas = document.getElementById('catan-board-canvas')
  const boardRenderer = new CatanBoardRenderer(canvas)

  const PLAYER_COLORS = ['#e63946', '#457b9d', '#2a9d8f', '#e9c46a']
  boardRenderer.setPlayerColors(PLAYER_COLORS)

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------
  const ui = new CatanUI(document.getElementById('catan-ui-container'), {
    onAction: (action) => {
      if (action._ui_build) {
        // Build-menu button clicked — map to the appropriate board highlight mode
        handleBuildRequest(action._ui_build)
      } else {
        wsClient.sendAction(action)
      }
    },
  })

  // ---------------------------------------------------------------------------
  // WebSocket client
  // ---------------------------------------------------------------------------
  let myPlayerIndex = null

  // Observers connect to a separate read-only WS endpoint; they never get a
  // player index and all action callbacks are no-ops.
  const wsPath = isObserver ? `/catan/observe/${roomCode}` : null

  const wsClient = new CatanWSClient(roomCode, playerName, {
    wsPath: wsPath,
    onGameStateUpdate: (gameState) => {
      // Initialise board on first state update
      if (!boardRenderer.board) {
        boardRenderer.setBoard(gameState.board)
        // Switch to the game view for observers, or when reconnecting mid-game
        // (game area is still hidden but we just received a game state).
        const gameAreaEl = document.getElementById('game-area')
        if (isObserver || gameAreaEl?.classList.contains('hidden')) {
          document.getElementById('waiting-room')?.classList.add('hidden')
          gameAreaEl?.classList.remove('hidden')
          window.dispatchEvent(new Event('resize'))
        }
      } else {
        boardRenderer.updateBoard(gameState.board)
      }
      boardRenderer.setPlayerColors(
        gameState.players.map((p) => p.color || PLAYER_COLORS[p.player_index] || '#888'),
      )
      ui.setGameState(gameState, myPlayerIndex)
      updateLegalHighlights(gameState, boardRenderer, myPlayerIndex)
      // Log any events produced by the most recent action(s).
      if (Array.isArray(gameState.recent_events)) {
        gameState.recent_events.forEach((evt) => ui.updateLog(evt))
      }
    },

    onErrorMessage: (error) => {
      ui.showToast(error, 'error')
    },

    onPlayerJoined: (msg) => {
      ui.updateLog(`${msg.player_name} joined the room (${msg.total_players}/4 players)`)
      if (msg.player_name === playerName) {
        myPlayerIndex = msg.player_index
      }
      appendWaitingPlayer(msg)
      // Enable start button once >= 2 players are in
      const startBtn = document.getElementById('start-game-btn')
      if (startBtn && msg.total_players >= 2) startBtn.disabled = false
    },

    onGameStarted: (msg) => {
      ui.updateLog('🎮 Game started!')
      // Switch from waiting room to game board
      document.getElementById('waiting-room')?.classList.add('hidden')
      document.getElementById('game-area')?.classList.remove('hidden')
      // Trigger a resize so the board fills its container
      window.dispatchEvent(new Event('resize'))
    },

    onGameOver: (msg) => {
      const iAmWinner = msg.winner_player_index === myPlayerIndex
      ui.showGameOver(msg.winner_name, iAmWinner)
      ui.updateLog(
        `🏆 ${msg.winner_name} wins with ${msg.final_victory_points[msg.winner_player_index]} VPs!`,
      )
    },

    onConnectionChange: (status) => {
      const statusEl = document.getElementById('connection-status')
      if (!statusEl) return
      const labels = {
        connected: '🟢 Connected',
        disconnected: '🔴 Disconnected',
        reconnecting: '🟡 Reconnecting…',
        error: '🔴 Connection error',
        failed: '🔴 Connection failed',
      }
      statusEl.textContent = labels[status] || status

      // When auto-reconnect is exhausted, show the manual rejoin prompt.
      const rejoinPrompt = document.getElementById('rejoin-prompt')
      if (rejoinPrompt) {
        rejoinPrompt.style.display = status === 'failed' ? 'block' : 'none'
      }
    },

    onTradeProposed: (msg) => {
      ui.setActiveTrade({
        trade_id: msg.trade_id,
        offering_player: msg.offering_player,
        offering: msg.offering,
        requesting: msg.requesting,
        target_player: msg.target_player,
      })
      const offeringPlayer = ui.gameState?.players[msg.offering_player]
      if (offeringPlayer && msg.offering_player !== myPlayerIndex) {
        ui.updateLog(`🤝 ${offeringPlayer.name} proposed a trade`)
      }
    },

    onTradeAccepted: (msg) => {
      ui.setActiveTrade(null)
      const offeringPlayer = ui.gameState?.players[msg.offering_player]
      const acceptingPlayer = ui.gameState?.players[msg.accepting_player]
      if (offeringPlayer && acceptingPlayer) {
        ui.updateLog(`✅ ${acceptingPlayer.name} accepted ${offeringPlayer.name}'s trade`)
        ui.showToast('Trade completed!', 'success')
      }
    },

    onTradeRejected: (msg) => {
      const rejectingPlayer = ui.gameState?.players[msg.rejecting_player]
      if (rejectingPlayer && msg.rejecting_player !== myPlayerIndex) {
        ui.updateLog(`❌ ${rejectingPlayer.name} rejected the trade`)
      }
      if (ui.activeTrade && ui.activeTrade.trade_id === msg.trade_id) {
        if (msg.rejecting_player === myPlayerIndex) {
          ui.setActiveTrade(null)
        }
      }
    },

    onTradeCancelled: (msg) => {
      ui.setActiveTrade(null)
      const offeringPlayer = ui.gameState?.players[msg.offering_player]
      if (offeringPlayer && msg.offering_player !== myPlayerIndex) {
        ui.updateLog(`🚫 ${offeringPlayer.name} cancelled their trade offer`)
      }
    },
  })

  wsClient.connect()

  // ---------------------------------------------------------------------------
  // Board interaction → actions
  // ---------------------------------------------------------------------------

  boardRenderer.onVertexClick = (vertexId) => {
    if (myPlayerIndex === null || !ui.gameState) return
    const gs = ui.gameState
    if (gs.turn_state.player_index !== myPlayerIndex) return

    const pending = gs.turn_state.pending_action
    const phase = gs.phase

    // Setup phase: always place settlement
    if (phase === 'setup_forward' || phase === 'setup_backward') {
      if (pending === 'place_settlement') {
        wsClient.sendAction({
          action_type: 'place_settlement',
          player_index: myPlayerIndex,
          vertex_id: vertexId,
        })
      }
      return
    }

    // Main phase: settlement or city depending on what's at the vertex
    if (pending === 'build_or_trade') {
      const vertex = gs.board.vertices.find((v) => v.vertex_id === vertexId)
      if (vertex && vertex.building && vertex.building.player_index === myPlayerIndex) {
        // Upgrade to city
        wsClient.sendAction({
          action_type: 'place_city',
          player_index: myPlayerIndex,
          vertex_id: vertexId,
        })
      } else {
        wsClient.sendAction({
          action_type: 'place_settlement',
          player_index: myPlayerIndex,
          vertex_id: vertexId,
        })
      }
    }
  }

  boardRenderer.onEdgeClick = (edgeId) => {
    if (myPlayerIndex === null || !ui.gameState) return
    const gs = ui.gameState
    if (gs.turn_state.player_index !== myPlayerIndex) return
    const pending = gs.turn_state.pending_action
    if (pending === 'place_road' || pending === 'build_or_trade') {
      wsClient.sendAction({
        action_type: 'place_road',
        player_index: myPlayerIndex,
        edge_id: edgeId,
      })
    }
  }

  boardRenderer.onTileClick = (tileIndex) => {
    if (myPlayerIndex === null || !ui.gameState) return
    const gs = ui.gameState
    if (gs.turn_state.player_index !== myPlayerIndex) return
    if (gs.turn_state.pending_action !== 'move_robber') return
    wsClient.sendAction({
      action_type: 'move_robber',
      player_index: myPlayerIndex,
      tile_index: tileIndex,
    })
  }

  // ---------------------------------------------------------------------------
  // Waiting room buttons
  // ---------------------------------------------------------------------------

  const startBtn = document.getElementById('start-game-btn')
  if (startBtn) {
    startBtn.addEventListener('click', async () => {
      startBtn.disabled = true
      try {
        const resp = await fetch(`/catan/rooms/${roomCode}/start`, { method: 'POST' })
        if (!resp.ok) {
          const data = await resp.json()
          ui.showToast(data.detail || 'Failed to start game', 'error')
          startBtn.disabled = false
        }
      } catch (err) {
        ui.showToast('Failed to start game', 'error')
        startBtn.disabled = false
      }
    })
  }

  const addAiBtn = document.getElementById('add-ai-btn')
  const aiModal = document.getElementById('ai-difficulty-modal')
  const aiModalCancel = document.getElementById('ai-modal-cancel')

  if (addAiBtn && aiModal) {
    // Show modal when Add AI button is clicked
    addAiBtn.addEventListener('click', () => {
      aiModal.style.display = 'flex'
    })

    // Handle difficulty button clicks
    aiModal.querySelectorAll('[data-difficulty]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const difficulty = btn.dataset.difficulty
        addAiBtn.disabled = true
        aiModal.style.display = 'none'

        try {
          const resp = await fetch(`/catan/rooms/${roomCode}/add-ai?difficulty=${difficulty}`, {
            method: 'POST',
          })
          if (!resp.ok) {
            const data = await resp.json()
            ui.showToast(data.detail || 'Failed to add AI', 'error')
          }
        } catch (err) {
          ui.showToast('Failed to add AI', 'error')
        } finally {
          addAiBtn.disabled = false
        }
      })
    })

    // Handle cancel button
    if (aiModalCancel) {
      aiModalCancel.addEventListener('click', () => {
        aiModal.style.display = 'none'
      })
    }
  }

  // ---------------------------------------------------------------------------
  // Build-request handler (closure over wsClient + myPlayerIndex)
  // ---------------------------------------------------------------------------

  /**
   * Called when the player clicks a build-menu button.
   * For dev card purchases the WS action is sent immediately.
   * For placements a brief hint is shown to guide the player to click the board.
   */
  function handleBuildRequest(buildType) {
    if (buildType === 'dev_card') {
      wsClient.sendAction({ action_type: 'build_dev_card', player_index: myPlayerIndex })
      return
    }
    const hints = {
      road: 'Click a highlighted edge to place your road.',
      settlement: 'Click a highlighted vertex to place your settlement.',
      city: 'Click a highlighted vertex (your settlement) to upgrade to a city.',
    }
    const hintEl = document.getElementById('catan-build-hint')
    if (hintEl) {
      hintEl.textContent = hints[buildType] || ''
      hintEl.style.display = 'block'
      setTimeout(() => {
        hintEl.style.display = 'none'
      }, 4000)
    }
  }
}

/** Update board legal-action highlights from the current game state. */
function updateLegalHighlights(gameState, boardRenderer, myPlayerIndex) {
  if (myPlayerIndex === null || gameState.turn_state.player_index !== myPlayerIndex) {
    boardRenderer.setLegalVertices([])
    boardRenderer.setLegalEdges([])
    boardRenderer.setLegalTiles([])
    return
  }

  // If the server provides pre-computed legal IDs use them; otherwise clear.
  const pending = gameState.turn_state.pending_action
  const legalVertices = gameState.legal_vertex_ids || []
  const legalEdges = gameState.legal_edge_ids || []
  const legalTiles = gameState.legal_tile_indices || []

  if (pending === 'place_settlement') {
    boardRenderer.setLegalVertices(legalVertices)
    boardRenderer.setLegalEdges([])
    boardRenderer.setLegalTiles([])
  } else if (pending === 'place_road') {
    boardRenderer.setLegalVertices([])
    boardRenderer.setLegalEdges(legalEdges)
    boardRenderer.setLegalTiles([])
  } else if (pending === 'move_robber') {
    boardRenderer.setLegalVertices([])
    boardRenderer.setLegalEdges([])
    boardRenderer.setLegalTiles(legalTiles)
  } else if (pending === 'build_or_trade') {
    // Highlight all legal build spots so the player can see possibilities
    boardRenderer.setLegalVertices(legalVertices)
    boardRenderer.setLegalEdges(legalEdges)
    boardRenderer.setLegalTiles([])
  } else {
    boardRenderer.setLegalVertices([])
    boardRenderer.setLegalEdges([])
    boardRenderer.setLegalTiles([])
  }
}

/** Add a player row to the waiting-room player list. */
function appendWaitingPlayer(msg) {
  const list = document.getElementById('waiting-players-list')
  if (!list) return
  // Avoid duplicates
  if (list.querySelector(`[data-player-index="${msg.player_index}"]`)) return
  const div = document.createElement('div')
  div.className = 'waiting-player'
  div.dataset.playerIndex = msg.player_index
  div.textContent = `👤 ${msg.player_name} (Player ${msg.player_index + 1})`
  list.appendChild(div)
}
