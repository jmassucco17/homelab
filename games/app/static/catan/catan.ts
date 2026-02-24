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

import { CatanBoardRenderer } from './board.js'
import { CatanUI, GameState } from './ui.js'
import { CatanWSClient } from './ws_client.js'

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('catan-lobby')) {
    initLobby()
  } else if (document.getElementById('catan-game-area')) {
    initGame()
  }
})

// ---------------------------------------------------------------------------
// Lobby
// ---------------------------------------------------------------------------

function initLobby(): void {
  const createBtn = document.getElementById('btn-create-room') as HTMLButtonElement | null
  const joinBtn = document.getElementById('join-room-btn') as HTMLButtonElement | null
  const joinCodeInput = document.getElementById('join-room-code') as HTMLInputElement | null
  const nameInput = document.getElementById('player-name-input') as HTMLInputElement | null
  const errorEl = document.getElementById('lobby-error')

  function getName(): string {
    return nameInput ? nameInput.value.trim() : ''
  }

  function showError(msg: string): void {
    if (errorEl) {
      errorEl.textContent = msg
      errorEl.style.display = 'block'
    }
  }

  function hideError(): void {
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
      if (!code || code.length !== 4 || !/^[A-Z]{4}$/.test(code)) {
        showError('Enter a valid 4-letter room code.')
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
}

// ---------------------------------------------------------------------------
// Game page
// ---------------------------------------------------------------------------

async function initGame(): Promise<void> {
  const params = new URLSearchParams(window.location.search)
  const roomCode = params.get('room')
  const playerName = params.get('name') || 'Player'

  if (!roomCode) {
    window.location.href = '/catan'
    return
  }

  // Show room code in waiting room header
  const rcEl = document.getElementById('room-code-display')
  if (rcEl) rcEl.textContent = roomCode

  // ---------------------------------------------------------------------------
  // Board renderer
  // ---------------------------------------------------------------------------
  const canvas = document.getElementById('catan-board-canvas') as HTMLCanvasElement
  const boardRenderer = new CatanBoardRenderer(canvas)

  const PLAYER_COLORS = ['#e63946', '#457b9d', '#2a9d8f', '#e9c46a']
  boardRenderer.setPlayerColors(PLAYER_COLORS)

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------
  const ui = new CatanUI(document.getElementById('catan-ui-container') as HTMLElement, {
    onAction: (action) => {
      if (action._ui_build) {
        // Build-menu button clicked — map to the appropriate board highlight mode
        handleBuildRequest(action._ui_build as string)
      } else {
        wsClient.sendAction(action)
      }
    },
  })

  // ---------------------------------------------------------------------------
  // WebSocket client
  // ---------------------------------------------------------------------------
  let myPlayerIndex: number | null = null

  const wsClient = new CatanWSClient(roomCode, playerName, {
    onGameStateUpdate: (gameState) => {
      const gs = gameState as GameState
      // Initialise board on first state update
      if (!boardRenderer.board) {
        boardRenderer.setBoard(gs.board)
      } else {
        boardRenderer.updateBoard(gs.board)
      }
      boardRenderer.setPlayerColors(
        gs.players.map((p) => p.color || PLAYER_COLORS[p.player_index] || '#888'),
      )
      ui.setGameState(gs, myPlayerIndex)
      updateLegalHighlights(gs, boardRenderer, myPlayerIndex)
    },

    onErrorMessage: (error) => {
      ui.showToast(error, 'error')
    },

    onPlayerJoined: (msg) => {
      ui.updateLog(`${String(msg.player_name)} joined the room (${String(msg.total_players)}/4 players)`)
      if (msg.player_name === playerName) {
        myPlayerIndex = msg.player_index as number
      }
      appendWaitingPlayer(msg)
      // Enable start button once >= 2 players are in
      const startBtnEl = document.getElementById('start-game-btn') as HTMLButtonElement | null
      if (startBtnEl && (msg.total_players as number) >= 2) startBtnEl.disabled = false
    },

    onGameStarted: () => {
      ui.updateLog('🎮 Game started!')
      // Switch from waiting room to game board
      document.getElementById('waiting-room')?.classList.add('hidden')
      document.getElementById('game-area')?.classList.remove('hidden')
      // Trigger a resize so the board fills its container
      window.dispatchEvent(new Event('resize'))
    },

    onGameOver: (msg) => {
      const iAmWinner = msg.winner_player_index === myPlayerIndex
      ui.showGameOver(msg.winner_name as string, iAmWinner)
      const vpMap = msg.final_victory_points as Record<number, number>
      ui.updateLog(
        `🏆 ${String(msg.winner_name)} wins with ${vpMap[msg.winner_player_index as number]} VPs!`,
      )
    },

    onConnectionChange: (status) => {
      const statusEl = document.getElementById('connection-status')
      if (!statusEl) return
      const labels: Record<string, string> = {
        connected: '🟢 Connected',
        disconnected: '🔴 Disconnected',
        reconnecting: '🟡 Reconnecting…',
        error: '🔴 Connection error',
        failed: '🔴 Connection failed',
      }
      statusEl.textContent = labels[status] || status
    },

    onTradeProposed: (msg) => {
      ui.setActiveTrade({
        trade_id: msg.trade_id as string,
        offering_player: msg.offering_player as number,
        offering: msg.offering as Record<string, number>,
        requesting: msg.requesting as Record<string, number>,
        target_player: msg.target_player as number | null,
      })
      const offeringPlayer = ui.gameState?.players[msg.offering_player as number]
      if (offeringPlayer && msg.offering_player !== myPlayerIndex) {
        ui.updateLog(`🤝 ${offeringPlayer.name} proposed a trade`)
      }
    },

    onTradeAccepted: (msg) => {
      ui.setActiveTrade(null)
      const offeringPlayer = ui.gameState?.players[msg.offering_player as number]
      const acceptingPlayer = ui.gameState?.players[msg.accepting_player as number]
      if (offeringPlayer && acceptingPlayer) {
        ui.updateLog(`✅ ${acceptingPlayer.name} accepted ${offeringPlayer.name}'s trade`)
        ui.showToast('Trade completed!', 'success')
      }
    },

    onTradeRejected: (msg) => {
      const rejectingPlayer = ui.gameState?.players[msg.rejecting_player as number]
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
      const offeringPlayer = ui.gameState?.players[msg.offering_player as number]
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
    const idx = myPlayerIndex
    if (idx === null || !ui.gameState) return
    const gs = ui.gameState
    if (gs.turn_state.player_index !== idx) return

    const pending = gs.turn_state.pending_action
    const phase = gs.phase

    // Setup phase: always place settlement
    if (phase === 'setup_forward' || phase === 'setup_backward') {
      if (pending === 'place_settlement') {
        wsClient.sendAction({
          action_type: 'place_settlement',
          player_index: idx,
          vertex_id: vertexId,
        })
      }
      return
    }

    // Main phase: settlement or city depending on what's at the vertex
    if (pending === 'build_or_trade') {
      const vertex = gs.board.vertices.find((v) => v.vertex_id === vertexId)
      if (vertex && vertex.building && vertex.building.player_index === idx) {
        // Upgrade to city
        wsClient.sendAction({
          action_type: 'place_city',
          player_index: idx,
          vertex_id: vertexId,
        })
      } else {
        wsClient.sendAction({
          action_type: 'place_settlement',
          player_index: idx,
          vertex_id: vertexId,
        })
      }
    }
  }

  boardRenderer.onEdgeClick = (edgeId) => {
    const idx = myPlayerIndex
    if (idx === null || !ui.gameState) return
    const gs = ui.gameState
    if (gs.turn_state.player_index !== idx) return
    const pending = gs.turn_state.pending_action
    if (pending === 'place_road' || pending === 'build_or_trade') {
      wsClient.sendAction({
        action_type: 'place_road',
        player_index: idx,
        edge_id: edgeId,
      })
    }
  }

  boardRenderer.onTileClick = (tileIndex) => {
    const idx = myPlayerIndex
    if (idx === null || !ui.gameState) return
    wsClient.sendAction({
      action_type: 'move_robber',
      player_index: idx,
      tile_index: tileIndex,
    })
  }

  // ---------------------------------------------------------------------------
  // Waiting room buttons
  // ---------------------------------------------------------------------------

  const startBtn = document.getElementById('start-game-btn') as HTMLButtonElement | null
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
      } catch {
        ui.showToast('Failed to start game', 'error')
        startBtn.disabled = false
      }
    })
  }

  const addAiBtn = document.getElementById('add-ai-btn') as HTMLButtonElement | null
  const aiModal = document.getElementById('ai-difficulty-modal')
  const aiModalCancel = document.getElementById('ai-modal-cancel')

  if (addAiBtn && aiModal) {
    // Show modal when Add AI button is clicked
    addAiBtn.addEventListener('click', () => {
      aiModal.style.display = 'flex'
    })

    // Handle difficulty button clicks
    aiModal.querySelectorAll('[data-difficulty]').forEach((rawBtn) => {
      const btn = rawBtn as HTMLButtonElement
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
        } catch {
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
  function handleBuildRequest(buildType: string): void {
    if (buildType === 'dev_card') {
      wsClient.sendAction({ action_type: 'build_dev_card', player_index: myPlayerIndex })
      return
    }
    const hints: Record<string, string> = {
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
function updateLegalHighlights(
  gameState: GameState,
  boardRenderer: CatanBoardRenderer,
  myPlayerIndex: number | null,
): void {
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
function appendWaitingPlayer(msg: Record<string, unknown>): void {
  const list = document.getElementById('waiting-players-list')
  if (!list) return
  // Avoid duplicates
  if (list.querySelector(`[data-player-index="${msg.player_index}"]`)) return
  const div = document.createElement('div')
  div.className = 'waiting-player'
  div.dataset.playerIndex = String(msg.player_index)
  div.textContent = `👤 ${String(msg.player_name)} (Player ${Number(msg.player_index) + 1})`
  list.appendChild(div)
}
