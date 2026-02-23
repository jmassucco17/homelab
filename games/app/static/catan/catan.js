/**
 * Catan lobby JavaScript — Phase 6 will implement the full board renderer,
 * UI components, and WebSocket client.  This file handles lobby interactions:
 * creating rooms, joining rooms via HTTP, and opening the WebSocket connection.
 */

'use strict'

const API_BASE = ''

// ---------------------------------------------------------------------------
// Element references
// ---------------------------------------------------------------------------
const btnCreate = document.getElementById('btn-create-room')
const roomCodeDisplay = document.getElementById('room-code-display')
const createResult = document.getElementById('create-room-result')

const inputRoomCode = document.getElementById('input-room-code')
const inputPlayerName = document.getElementById('input-player-name')
const btnJoin = document.getElementById('btn-join-room')
const joinError = document.getElementById('join-room-error')

const waitingRoom = document.getElementById('waiting-room')
const waitingRoomCode = document.getElementById('waiting-room-code')
const playerList = document.getElementById('player-list')
const waitingMsg = document.getElementById('waiting-msg')
const btnStart = document.getElementById('btn-start-game')
const btnAddAI = document.getElementById('btn-add-ai')

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentRoomCode = null
let currentPlayerName = null
let isCreator = false
let ws = null

// ---------------------------------------------------------------------------
// Create room
// ---------------------------------------------------------------------------
btnCreate.addEventListener('click', async () => {
  try {
    const resp = await fetch(`${API_BASE}/catan/rooms`, { method: 'POST' })
    if (!resp.ok) throw new Error('Failed to create room')
    const data = await resp.json()
    roomCodeDisplay.textContent = data.room_code
    createResult.style.display = ''
    inputRoomCode.value = data.room_code
    isCreator = true
  } catch (err) {
    showJoinError(`Error: ${err.message}`)
  }
})

// ---------------------------------------------------------------------------
// Join room
// ---------------------------------------------------------------------------
btnJoin.addEventListener('click', () => {
  const code = inputRoomCode.value.trim().toUpperCase()
  const name = inputPlayerName.value.trim()
  if (!code || code.length !== 4) {
    showJoinError('Enter a valid 4-character room code.')
    return
  }
  if (!name) {
    showJoinError('Enter your player name.')
    return
  }
  joinError.style.display = 'none'
  connectWebSocket(code, name)
})

// ---------------------------------------------------------------------------
// WebSocket connection
// ---------------------------------------------------------------------------
function connectWebSocket(roomCode, playerName) {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${protocol}://${location.host}/catan/ws/${roomCode}/${encodeURIComponent(playerName)}`
  ws = new WebSocket(url)

  ws.addEventListener('open', () => {
    currentRoomCode = roomCode
    currentPlayerName = playerName
    showWaitingRoom(roomCode)
  })

  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data)
    handleServerMessage(msg)
  })

  ws.addEventListener('close', () => {
    waitingMsg.textContent = 'Disconnected from server.'
  })

  ws.addEventListener('error', () => {
    showJoinError('Could not connect to room. Check the room code and try again.')
  })
}

// ---------------------------------------------------------------------------
// Server message handling
// ---------------------------------------------------------------------------
function handleServerMessage(msg) {
  switch (msg.message_type) {
    case 'player_joined':
      addPlayerToList(msg.player_name)
      updateStartButton(msg.total_players)
      break
    case 'game_started':
      waitingMsg.textContent = 'Game starting…'
      // Phase 6 will redirect to the game board view.
      break
    case 'error_message':
      showJoinError(msg.error)
      break
    default:
      break
  }
}

// ---------------------------------------------------------------------------
// Waiting room UI helpers
// ---------------------------------------------------------------------------
function showWaitingRoom(roomCode) {
  waitingRoom.style.display = ''
  waitingRoomCode.textContent = roomCode
}

function addPlayerToList(name) {
  const li = document.createElement('li')
  li.textContent = name
  playerList.appendChild(li)
}

function updateStartButton(totalPlayers) {
  if (isCreator && totalPlayers >= 2) {
    btnStart.style.display = ''
    btnAddAI.style.display = ''
    waitingMsg.textContent = `${totalPlayers} player(s) joined. Ready to start!`
  }
}

function showJoinError(msg) {
  joinError.textContent = msg
  joinError.style.display = ''
}

// ---------------------------------------------------------------------------
// Start game
// ---------------------------------------------------------------------------
btnStart.addEventListener('click', async () => {
  if (!currentRoomCode) return
  try {
    const resp = await fetch(`${API_BASE}/catan/rooms/${currentRoomCode}/start`, {
      method: 'POST',
    })
    if (!resp.ok) {
      const err = await resp.json()
      showJoinError(err.detail || 'Failed to start game')
    }
  } catch (err) {
    showJoinError(`Error: ${err.message}`)
  }
})
