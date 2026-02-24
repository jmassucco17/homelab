/**
 * Catan WebSocket client.
 *
 * Manages the connection to the game server, dispatches incoming messages,
 * and provides a simple API for sending player actions.
 *
 * Features:
 *  - Automatic exponential-backoff reconnection (up to maxReconnectAttempts)
 *  - Typed callbacks for every server message type
 *  - Uses wss:// automatically when the page is served over HTTPS
 */

interface Options {
  onGameStateUpdate?: (gameState: unknown) => void
  onErrorMessage?: (error: string) => void
  onPlayerJoined?: (msg: Record<string, unknown>) => void
  onGameStarted?: (msg: Record<string, unknown>) => void
  onGameOver?: (msg: Record<string, unknown>) => void
  onConnectionChange?: (status: string) => void
  onTradeProposed?: (msg: Record<string, unknown>) => void
  onTradeAccepted?: (msg: Record<string, unknown>) => void
  onTradeRejected?: (msg: Record<string, unknown>) => void
  onTradeCancelled?: (msg: Record<string, unknown>) => void
}

export class CatanWSClient {
  roomCode: string
  playerName: string
  ws: WebSocket | null
  reconnectAttempts: number
  maxReconnectAttempts: number
  _reconnectTimer: ReturnType<typeof setTimeout> | null
  _closed: boolean

  onGameStateUpdate: (gameState: unknown) => void
  onErrorMessage: (error: string) => void
  onPlayerJoined: (msg: Record<string, unknown>) => void
  onGameStarted: (msg: Record<string, unknown>) => void
  onGameOver: (msg: Record<string, unknown>) => void
  onConnectionChange: (status: string) => void
  onTradeProposed: (msg: Record<string, unknown>) => void
  onTradeAccepted: (msg: Record<string, unknown>) => void
  onTradeRejected: (msg: Record<string, unknown>) => void
  onTradeCancelled: (msg: Record<string, unknown>) => void

  constructor(roomCode: string, playerName: string, options: Options = {}) {
    this.roomCode = roomCode
    this.playerName = playerName

    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 8
    this._reconnectTimer = null
    this._closed = false

    this.onGameStateUpdate = options.onGameStateUpdate || (() => {})
    this.onErrorMessage = options.onErrorMessage || (() => {})
    this.onPlayerJoined = options.onPlayerJoined || (() => {})
    this.onGameStarted = options.onGameStarted || (() => {})
    this.onGameOver = options.onGameOver || (() => {})
    this.onConnectionChange = options.onConnectionChange || (() => {})
    this.onTradeProposed = options.onTradeProposed || (() => {})
    this.onTradeAccepted = options.onTradeAccepted || (() => {})
    this.onTradeRejected = options.onTradeRejected || (() => {})
    this.onTradeCancelled = options.onTradeCancelled || (() => {})
  }

  // -------------------------------------------------------------------------
  // Connection management
  // -------------------------------------------------------------------------

  /** Open (or re-open) the WebSocket connection. */
  connect(): void {
    this._closed = false
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${protocol}://${host}/catan/ws/${encodeURIComponent(this.roomCode)}/${encodeURIComponent(this.playerName)}`

    this.ws = new WebSocket(url)

    this.ws.addEventListener('open', () => {
      this.reconnectAttempts = 0
      this.onConnectionChange('connected')
    })

    this.ws.addEventListener('message', (event) => {
      try {
        const msg = JSON.parse(event.data) as Record<string, unknown>
        this._dispatch(msg)
      } catch (err) {
        console.error('[CatanWS] Failed to parse message:', err)
      }
    })

    this.ws.addEventListener('close', () => {
      this.onConnectionChange('disconnected')
      if (!this._closed) this._scheduleReconnect()
    })

    this.ws.addEventListener('error', () => {
      this.onConnectionChange('error')
    })
  }

  /** Permanently close the connection (no reconnect). */
  disconnect(): void {
    this._closed = true
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
      this._reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  // -------------------------------------------------------------------------
  // Sending messages
  // -------------------------------------------------------------------------

  /** Send a game action to the server. */
  sendAction(action: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[CatanWS] Not connected — action dropped:', action)
      return
    }
    const msg = { message_type: 'submit_action', action }
    this.ws.send(JSON.stringify(msg))
  }

  // -------------------------------------------------------------------------
  // Message dispatch
  // -------------------------------------------------------------------------

  _dispatch(msg: Record<string, unknown>): void {
    switch (msg.message_type) {
      case 'game_state_update':
        this.onGameStateUpdate(msg.game_state)
        break
      case 'error_message':
        this.onErrorMessage(msg.error as string)
        break
      case 'player_joined':
        this.onPlayerJoined(msg)
        break
      case 'game_started':
        this.onGameStarted(msg)
        break
      case 'game_over':
        this.onGameOver(msg)
        break
      case 'trade_proposed':
        this.onTradeProposed(msg)
        break
      case 'trade_accepted':
        this.onTradeAccepted(msg)
        break
      case 'trade_rejected':
        this.onTradeRejected(msg)
        break
      case 'trade_cancelled':
        this.onTradeCancelled(msg)
        break
      default:
        console.warn('[CatanWS] Unknown message type:', msg.message_type)
    }
  }

  // -------------------------------------------------------------------------
  // Reconnection
  // -------------------------------------------------------------------------

  _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[CatanWS] Max reconnect attempts reached.')
      this.onConnectionChange('failed')
      return
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
    this.reconnectAttempts++
    console.log(`[CatanWS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})…`)
    this.onConnectionChange('reconnecting')
    this._reconnectTimer = setTimeout(() => this.connect(), delay)
  }
}
