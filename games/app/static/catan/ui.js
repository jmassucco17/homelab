/**
 * Catan UI components — player hand panel, build menu, trade panel,
 * dice display, action buttons and toast notifications.
 */

'use strict'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RESOURCE_EMOJIS = {
  wood: '🌲',
  brick: '🧱',
  wheat: '🌾',
  sheep: '🐑',
  ore: '⛰️',
}

const BUILD_COSTS = {
  road: { wood: 1, brick: 1 },
  settlement: { wood: 1, brick: 1, wheat: 1, sheep: 1 },
  city: { wheat: 2, ore: 3 },
  dev_card: { wheat: 1, sheep: 1, ore: 1 },
}

const DEV_CARD_LABELS = {
  knight: '⚔️ Knight',
  road_building: '🛤️ Road Building',
  year_of_plenty: '🌟 Year of Plenty',
  monopoly: '💰 Monopoly',
  victory_point: '🏆 Victory Point',
}

const RESOURCE_OPTIONS = ['wood', 'brick', 'wheat', 'sheep', 'ore']

// ---------------------------------------------------------------------------
// HTML helpers
// ---------------------------------------------------------------------------

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = String(text)
  return div.innerHTML
}

function costStr(cost) {
  return Object.entries(cost)
    .flatMap(([r, n]) => Array(n).fill(RESOURCE_EMOJIS[r] || r))
    .join(' ')
}

// ---------------------------------------------------------------------------
// CatanUI class
// ---------------------------------------------------------------------------

export class CatanUI {
  /**
   * @param {HTMLElement} container  root element for UI sections
   * @param {object} options
   * @param {(action: object) => void} options.onAction  called with a raw action object
   */
  constructor(container, options = {}) {
    this.container = container
    /** @type {object|null} */
    this.gameState = null
    /** @type {number|null} */
    this.myPlayerIndex = null
    this.onAction = options.onAction || (() => {})
    /** @type {object|null} */
    this.activeTrade = null
    /** @type {object|null} Track previous resource counts for change detection */
    this.previousResources = null
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Update the rendered UI to reflect a new game state.
   * @param {object} gameState  deserialised GameState from the server
   * @param {number} myPlayerIndex
   */
  setGameState(gameState, myPlayerIndex) {
    this.gameState = gameState
    this.myPlayerIndex = myPlayerIndex
    this._renderAll()
  }

  /**
   * Show a transient toast notification.
   * @param {string} message
   * @param {'info'|'error'|'success'} type
   */
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container')
    if (!container) return
    const toast = document.createElement('div')
    toast.className = `toast toast-${type}`
    toast.textContent = message
    container.appendChild(toast)
    // Force a reflow so the browser registers the initial state before the
    // CSS transition runs (without this the element starts already visible).
    void toast.offsetHeight
    toast.classList.add('toast-visible')
    setTimeout(() => {
      toast.classList.remove('toast-visible')
      setTimeout(() => toast.remove(), 350)
    }, 3200)
  }

  /**
   * Show the game-over overlay.
   * @param {string} winnerName
   * @param {boolean} iAmWinner
   */
  showGameOver(winnerName, iAmWinner) {
    const overlay = document.getElementById('catan-game-over')
    if (!overlay) return
    overlay.style.display = 'flex'
    const msg = document.getElementById('game-over-message')
    if (msg) {
      msg.textContent = iAmWinner ? `🏆 You win, ${winnerName}!` : `Game over — ${winnerName} wins!`
    }
  }

  /**
   * Append a line to the action-history log.
   * @param {string} message
   */
  updateLog(message) {
    const log = document.getElementById('catan-action-log')
    if (!log) return
    const entry = document.createElement('div')
    entry.className = 'log-entry'
    entry.textContent = message
    log.appendChild(entry)
    log.scrollTop = log.scrollHeight
  }

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  _renderAll() {
    this._renderPlayers()
    this._renderHand()
    this._renderBuildMenu()
    this._renderActionButtons()
    this._renderDiceDisplay()
    this._renderTradeNotifications()
  }

  _renderPlayers() {
    const el = document.getElementById('catan-players-panel')
    if (!el || !this.gameState) return
    const { players, longest_road_owner, largest_army_owner, turn_state } = this.gameState
    el.innerHTML = players
      .map((p) => {
        const isActive = p.player_index === turn_state.player_index
        const isMe = p.player_index === this.myPlayerIndex
        const awards =
          (longest_road_owner === p.player_index ? '🛣️ ' : '') +
          (largest_army_owner === p.player_index ? '⚔️' : '')
        return `<div class="catan-player-row${isActive ? ' active-player' : ''}${isMe ? ' my-player' : ''}">
          <span class="player-dot" style="background:${escapeHtml(p.color)}"></span>
          <span class="player-name">${escapeHtml(p.name)}${isMe ? ' <em>(you)</em>' : ''}</span>
          <span class="player-vp">🏆 ${p.victory_points}</span>
          <span class="player-awards">${awards}</span>
          <span class="player-card-count">🃏 ${this._resourceTotal(p.resources)}</span>
        </div>`
      })
      .join('')
  }

  _renderHand() {
    const el = document.getElementById('catan-hand-panel')
    if (!el || this.myPlayerIndex === null || !this.gameState) return
    const player = this.gameState.players[this.myPlayerIndex]
    if (!player) return

    const res = player.resources
    const resHtml = RESOURCE_OPTIONS.map(
      (r) =>
        `<div class="resource-card" data-resource="${r}">
          <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
          <span class="res-count">${res[r] || 0}</span>
        </div>`,
    ).join('')

    const devCards = player.dev_cards || {}
    const newDevCards = player.new_dev_cards || {}
    const devHtml = Object.entries(devCards)
      .filter(([, n]) => n > 0)
      .map(([type, n]) => {
        const canPlay = this._canPlayDevCard(type)
        return `<div class="dev-card-item">
          <span>${DEV_CARD_LABELS[type] || type} ×${n}</span>
          ${canPlay ? `<button class="play-dev-btn" data-type="${type}">Play</button>` : ''}
        </div>`
      })
      .join('')

    // Show how many new (unplayable) dev cards were bought this turn
    const newTotal = Object.values(newDevCards).reduce((a, b) => a + b, 0)
    const newHtml = newTotal > 0 ? `<p class="new-dev-note">🆕 ${newTotal} new card(s) playable next turn</p>` : ''

    el.innerHTML = `<h3>Your Hand</h3>
      <div class="resource-cards">${resHtml}</div>
      ${devHtml ? `<div class="dev-cards">${devHtml}</div>` : ''}
      ${newHtml}`

    el.querySelectorAll('.play-dev-btn').forEach((btn) => {
      btn.addEventListener('click', () => this._handleDevCardPlay(btn.dataset.type))
    })

    // Animate resources that changed
    this._animateResourceChanges(res)
  }

  _renderBuildMenu() {
    const el = document.getElementById('catan-build-menu')
    if (!el || this.myPlayerIndex === null || !this.gameState) return
    const player = this.gameState.players[this.myPlayerIndex]
    if (!player) return

    const isMyTurn = this.gameState.turn_state.player_index === this.myPlayerIndex
    const hasRolled = this.gameState.turn_state.has_rolled
    const phase = this.gameState.phase
    const isMainPhase = phase === 'main'

    const canBuild = (cost) =>
      Object.entries(cost).every(([r, n]) => (player.resources[r] || 0) >= n)

    const items = [
      { key: 'road', label: '🛤️ Road', cost: BUILD_COSTS.road },
      { key: 'settlement', label: '🏠 Settlement', cost: BUILD_COSTS.settlement },
      { key: 'city', label: '🏙️ City', cost: BUILD_COSTS.city },
      { key: 'dev_card', label: '🃏 Dev Card', cost: BUILD_COSTS.dev_card },
    ]

    el.innerHTML =
      `<h3>Build</h3>` +
      items
        .map((item) => {
          const affordable = canBuild(item.cost)
          const active = isMyTurn && hasRolled && isMainPhase && affordable
          return `<button class="build-btn${affordable ? '' : ' unaffordable'}"
              data-action="${item.key}" ${active ? '' : 'disabled'}>
            ${item.label}
            <small class="build-cost">${costStr(item.cost)}</small>
          </button>`
        })
        .join('')

    el.querySelectorAll('.build-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.onAction({ _ui_build: btn.dataset.action })
      })
    })
  }

  _renderActionButtons() {
    const el = document.getElementById('catan-action-buttons')
    if (!el || !this.gameState) return
    el.innerHTML = ''

    const isMyTurn = this.gameState.turn_state.player_index === this.myPlayerIndex
    if (!isMyTurn) {
      el.innerHTML = '<p class="waiting-msg">⏳ Waiting for other player…</p>'
      return
    }

    const pending = this.gameState.turn_state.pending_action
    const hasRolled = this.gameState.turn_state.has_rolled

    if (pending === 'roll_dice') {
      const btn = document.createElement('button')
      btn.className = 'action-btn roll-btn'
      btn.textContent = '🎲 Roll Dice'
      btn.addEventListener('click', () =>
        this.onAction({ action_type: 'roll_dice', player_index: this.myPlayerIndex }),
      )
      el.appendChild(btn)
    }

    if (hasRolled && pending === 'build_or_trade') {
      const btn = document.createElement('button')
      btn.className = 'action-btn end-turn-btn'
      btn.textContent = '✅ End Turn'
      btn.addEventListener('click', () =>
        this.onAction({ action_type: 'end_turn', player_index: this.myPlayerIndex }),
      )
      el.appendChild(btn)

      // Bank trade shortcut
      const bankTradeBtn = document.createElement('button')
      bankTradeBtn.className = 'action-btn trade-btn'
      bankTradeBtn.textContent = '🔄 Bank Trade'
      bankTradeBtn.addEventListener('click', () => this._showBankTradeDialog())
      el.appendChild(bankTradeBtn)

      // Player trade button
      const playerTradeBtn = document.createElement('button')
      playerTradeBtn.className = 'action-btn trade-btn'
      playerTradeBtn.textContent = '🤝 Propose Trade'
      playerTradeBtn.addEventListener('click', () => this._showPlayerTradeDialog())
      el.appendChild(playerTradeBtn)
    }
  }

  _renderDiceDisplay() {
    const el = document.getElementById('catan-dice-display')
    if (!el || !this.gameState) return
    const roll = this.gameState.turn_state.roll_value
    if (roll !== null && roll !== undefined) {
      el.textContent = `🎲 ${roll}`
      el.classList.add('dice-rolled')
    } else {
      el.textContent = '🎲 —'
      el.classList.remove('dice-rolled')
    }
  }

  // -------------------------------------------------------------------------
  // Dev card and trade dialogs
  // -------------------------------------------------------------------------

  _canPlayDevCard(type) {
    if (!this.gameState || this.myPlayerIndex === null) return false
    if (type === 'victory_point') return false // VPs auto-count
    const isMyTurn = this.gameState.turn_state.player_index === this.myPlayerIndex
    if (!isMyTurn) return false
    const pending = this.gameState.turn_state.pending_action
    if (type === 'knight') return pending === 'roll_dice' || pending === 'build_or_trade'
    return pending === 'build_or_trade'
  }

  _handleDevCardPlay(type) {
    const idx = this.myPlayerIndex
    if (type === 'knight') {
      this.onAction({ action_type: 'play_knight', player_index: idx })
    } else if (type === 'road_building') {
      this.onAction({ action_type: 'play_road_building', player_index: idx })
    } else if (type === 'year_of_plenty') {
      this._showYearOfPlentyDialog()
    } else if (type === 'monopoly') {
      this._showMonopolyDialog()
    }
  }

  _showYearOfPlentyDialog() {
    const input = prompt(
      'Year of Plenty — choose 2 resources (comma-separated).\nOptions: wood, brick, wheat, sheep, ore',
    )
    if (!input) return
    const parts = input
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter((s) => RESOURCE_OPTIONS.includes(s))
    if (parts.length !== 2) {
      this.showToast('Enter exactly 2 valid resource names.', 'error')
      return
    }
    this.onAction({
      action_type: 'play_year_of_plenty',
      player_index: this.myPlayerIndex,
      resource1: parts[0],
      resource2: parts[1],
    })
  }

  _showMonopolyDialog() {
    const input = prompt(
      'Monopoly — choose a resource to take from all opponents.\nOptions: wood, brick, wheat, sheep, ore',
    )
    if (!input) return
    const res = input.trim().toLowerCase()
    if (!RESOURCE_OPTIONS.includes(res)) {
      this.showToast('Invalid resource name.', 'error')
      return
    }
    this.onAction({ action_type: 'play_monopoly', player_index: this.myPlayerIndex, resource: res })
  }

  _showBankTradeDialog() {
    const giving = prompt(
      'Bank Trade — which resource are you giving?\nOptions: wood, brick, wheat, sheep, ore',
    )
    if (!giving) return
    const giv = giving.trim().toLowerCase()
    if (!RESOURCE_OPTIONS.includes(giv)) {
      this.showToast('Invalid resource name.', 'error')
      return
    }
    const receiving = prompt(
      'Which resource do you want to receive?\nOptions: wood, brick, wheat, sheep, ore',
    )
    if (!receiving) return
    const rec = receiving.trim().toLowerCase()
    if (!RESOURCE_OPTIONS.includes(rec)) {
      this.showToast('Invalid resource name.', 'error')
      return
    }
    this.onAction({
      action_type: 'trade_with_bank',
      player_index: this.myPlayerIndex,
      giving: giv,
      receiving: rec,
    })
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  _resourceTotal(resources) {
    return Object.values(resources || {}).reduce((a, b) => a + b, 0)
  }

  _showPlayerTradeDialog() {
    if (!this.gameState || this.myPlayerIndex === null) return
    const player = this.gameState.players[this.myPlayerIndex]

    // Build resource selection strings
    const resStr = (res) => `${RESOURCE_EMOJIS[res]} ${res} (${player.resources[res] || 0})`

    // Ask what they're offering
    const offeringStr = prompt(
      'Propose Trade — What will you offer?\nFormat: resource:amount, resource:amount\nExample: wood:2, brick:1\n\nOptions: ' +
        RESOURCE_OPTIONS.map(resStr).join(', '),
    )
    if (!offeringStr) return
    const offering = this._parseResourceDict(offeringStr)
    if (!offering) {
      this.showToast('Invalid format. Use "resource:amount, resource:amount"', 'error')
      return
    }

    // Ask what they're requesting
    const requestingStr = prompt(
      'What do you want in return?\nFormat: resource:amount, resource:amount\nExample: wheat:1, ore:1\n\nOptions: ' +
        RESOURCE_OPTIONS.map((r) => `${RESOURCE_EMOJIS[r]} ${r}`).join(', '),
    )
    if (!requestingStr) return
    const requesting = this._parseResourceDict(requestingStr)
    if (!requesting) {
      this.showToast('Invalid format. Use "resource:amount, resource:amount"', 'error')
      return
    }

    // Ask which player (or all)
    const otherPlayers = this.gameState.players
      .filter((p) => p.player_index !== this.myPlayerIndex)
      .map((p) => `${p.player_index}: ${p.name}`)
      .join('\n')
    const targetStr = prompt(
      `Trade with which player?\nEnter player number, or leave blank to offer to all players.\n\n${otherPlayers}`,
    )

    let targetPlayer = null
    if (targetStr && targetStr.trim()) {
      targetPlayer = parseInt(targetStr.trim(), 10)
      if (
        isNaN(targetPlayer) ||
        targetPlayer === this.myPlayerIndex ||
        !this.gameState.players[targetPlayer]
      ) {
        this.showToast('Invalid player number.', 'error')
        return
      }
    }

    this.onAction({
      action_type: 'trade_offer',
      player_index: this.myPlayerIndex,
      offering,
      requesting,
      target_player: targetPlayer,
    })
  }

  _parseResourceDict(str) {
    try {
      const result = {}
      const pairs = str.split(',').map((s) => s.trim())
      for (const pair of pairs) {
        const [res, amtStr] = pair.split(':').map((s) => s.trim().toLowerCase())
        const amt = parseInt(amtStr, 10)
        if (!RESOURCE_OPTIONS.includes(res) || isNaN(amt) || amt <= 0) {
          return null
        }
        result[res] = (result[res] || 0) + amt
      }
      return Object.keys(result).length > 0 ? result : null
    } catch {
      return null
    }
  }

  _renderTradeNotifications() {
    const el = document.getElementById('catan-trade-notifications')
    if (!el) return
    if (!this.activeTrade) {
      el.innerHTML = ''
      el.style.display = 'none'
      return
    }

    const trade = this.activeTrade
    const offeringPlayer = this.gameState.players[trade.offering_player]
    const isMyTrade = trade.offering_player === this.myPlayerIndex
    const isTargeted = trade.target_player === null || trade.target_player === this.myPlayerIndex

    if (isMyTrade) {
      // Show cancel button for the offering player
      el.innerHTML = `<div class="trade-notification mine">
        <h4>🤝 Your Trade Offer</h4>
        <p><strong>Offering:</strong> ${this._formatResourceDict(trade.offering)}</p>
        <p><strong>Requesting:</strong> ${this._formatResourceDict(trade.requesting)}</p>
        <p><strong>Target:</strong> ${trade.target_player !== null ? this.gameState.players[trade.target_player].name : 'All players'}</p>
        <button class="trade-action-btn cancel-btn">❌ Cancel Trade</button>
      </div>`
      el.querySelector('.cancel-btn').addEventListener('click', () => {
        this.onAction({
          action_type: 'cancel_trade',
          player_index: this.myPlayerIndex,
          trade_id: trade.trade_id,
        })
      })
    } else if (isTargeted && !isMyTrade) {
      // Show accept/reject buttons for targeted players
      el.innerHTML = `<div class="trade-notification incoming">
        <h4>🤝 Trade Offer from ${escapeHtml(offeringPlayer.name)}</h4>
        <p><strong>They offer:</strong> ${this._formatResourceDict(trade.offering)}</p>
        <p><strong>They want:</strong> ${this._formatResourceDict(trade.requesting)}</p>
        <div class="trade-actions">
          <button class="trade-action-btn accept-btn">✅ Accept</button>
          <button class="trade-action-btn reject-btn">❌ Reject</button>
        </div>
      </div>`
      el.querySelector('.accept-btn').addEventListener('click', () => {
        this.onAction({
          action_type: 'accept_trade',
          player_index: this.myPlayerIndex,
          trade_id: trade.trade_id,
        })
      })
      el.querySelector('.reject-btn').addEventListener('click', () => {
        this.onAction({
          action_type: 'reject_trade',
          player_index: this.myPlayerIndex,
          trade_id: trade.trade_id,
        })
      })
    } else {
      // Not involved in this trade
      el.innerHTML = ''
      el.style.display = 'none'
      return
    }

    el.style.display = 'block'
  }

  _formatResourceDict(dict) {
    return Object.entries(dict)
      .map(([res, amt]) => `${RESOURCE_EMOJIS[res] || res} ×${amt}`)
      .join(', ')
  }

  /**
   * Update active trade state (called from message handlers).
   * @param {object|null} trade  PendingTrade data or null to clear
   */
  setActiveTrade(trade) {
    this.activeTrade = trade
    this._renderTradeNotifications()
  }

  /**
   * Animate resource cards when their counts change.
   * @param {object} currentResources  Current resource counts
   */
  _animateResourceChanges(currentResources) {
    if (!this.previousResources) {
      // First render, just store the current state
      this.previousResources = { ...currentResources }
      return
    }

    // Find which resources changed
    RESOURCE_OPTIONS.forEach((resource) => {
      const prev = this.previousResources[resource] || 0
      const curr = currentResources[resource] || 0
      if (prev !== curr) {
        // Trigger animation for this resource
        const card = document.querySelector(`.resource-card[data-resource="${resource}"]`)
        if (card) {
          // Remove the class first (in case it's already animating)
          card.classList.remove('resource-change')
          // Force reflow to restart animation
          void card.offsetHeight
          // Add the class to trigger animation
          card.classList.add('resource-change')
          // Remove the class after animation completes
          setTimeout(() => card.classList.remove('resource-change'), 500)
        }
      }
    })

    // Update stored resources
    this.previousResources = { ...currentResources }
  }
}
