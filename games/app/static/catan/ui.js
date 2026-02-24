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

const MAX_REQUESTING_AMOUNT = 10

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
    const modal = document.getElementById('year-of-plenty-modal')
    if (!modal) return

    const selected = []
    const picker = document.getElementById('yop-resources')
    const display = document.getElementById('yop-selection-display')
    const confirmBtn = document.getElementById('yop-confirm')
    const cancelBtn = document.getElementById('yop-cancel')

    picker.innerHTML = RESOURCE_OPTIONS.map(
      (r) =>
        `<button class="trade-res-btn" data-resource="${r}">
          <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
          <span class="res-name">${r}</span>
        </button>`,
    ).join('')

    const updateDisplay = () => {
      display.textContent =
        selected.length === 0
          ? 'Selected: none'
          : `Selected: ${selected.map((r) => RESOURCE_EMOJIS[r] + ' ' + r).join(', ')}`
      confirmBtn.disabled = selected.length !== 2
    }
    updateDisplay()

    picker.querySelectorAll('.trade-res-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (selected.length < 2) {
          selected.push(btn.dataset.resource)
          btn.classList.add('selected')
        } else {
          // Reset and start over
          selected.splice(0)
          picker.querySelectorAll('.trade-res-btn').forEach((b) => b.classList.remove('selected'))
          selected.push(btn.dataset.resource)
          btn.classList.add('selected')
        }
        updateDisplay()
      })
    })

    confirmBtn.onclick = () => {
      if (selected.length !== 2) return
      modal.style.display = 'none'
      this.onAction({
        action_type: 'play_year_of_plenty',
        player_index: this.myPlayerIndex,
        resource1: selected[0],
        resource2: selected[1],
      })
    }
    cancelBtn.onclick = () => {
      modal.style.display = 'none'
    }

    modal.style.display = 'flex'
  }

  _showMonopolyDialog() {
    const modal = document.getElementById('monopoly-modal')
    if (!modal) return

    let selected = null
    const picker = document.getElementById('monopoly-resources')
    const confirmBtn = document.getElementById('monopoly-confirm')
    const cancelBtn = document.getElementById('monopoly-cancel')

    picker.innerHTML = RESOURCE_OPTIONS.map(
      (r) =>
        `<button class="trade-res-btn" data-resource="${r}">
          <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
          <span class="res-name">${r}</span>
        </button>`,
    ).join('')
    confirmBtn.disabled = true

    picker.querySelectorAll('.trade-res-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        picker.querySelectorAll('.trade-res-btn').forEach((b) => b.classList.remove('selected'))
        btn.classList.add('selected')
        selected = btn.dataset.resource
        confirmBtn.disabled = false
      })
    })

    confirmBtn.onclick = () => {
      if (!selected) return
      modal.style.display = 'none'
      this.onAction({ action_type: 'play_monopoly', player_index: this.myPlayerIndex, resource: selected })
    }
    cancelBtn.onclick = () => {
      modal.style.display = 'none'
    }

    modal.style.display = 'flex'
  }

  _showBankTradeDialog() {
    const modal = document.getElementById('bank-trade-modal')
    if (!modal || !this.gameState || this.myPlayerIndex === null) return
    const player = this.gameState.players[this.myPlayerIndex]
    if (!player) return

    let selectedGiving = null
    let selectedReceiving = null

    const giveContainer = document.getElementById('bank-give-resources')
    const receiveSection = document.getElementById('bank-receive-section')
    const receiveContainer = document.getElementById('bank-receive-resources')
    const ratioDisplay = document.getElementById('bank-trade-ratio')
    const confirmBtn = document.getElementById('bank-trade-confirm')
    const cancelBtn = document.getElementById('bank-trade-cancel')

    // Reset state
    receiveSection.style.display = 'none'
    ratioDisplay.style.display = 'none'
    confirmBtn.disabled = true

    giveContainer.innerHTML = RESOURCE_OPTIONS.map((r) => {
      const count = player.resources[r] || 0
      return `<button class="trade-res-btn${count === 0 ? ' unaffordable' : ''}" data-resource="${r}" ${count === 0 ? 'disabled' : ''}>
          <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
          <span class="res-name">${r}</span>
          <span class="res-count">×${count}</span>
        </button>`
    }).join('')

    giveContainer.querySelectorAll('.trade-res-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        giveContainer.querySelectorAll('.trade-res-btn').forEach((b) => b.classList.remove('selected'))
        btn.classList.add('selected')
        selectedGiving = btn.dataset.resource
        selectedReceiving = null
        confirmBtn.disabled = true

        const ratio = this._getBankTradeRatio(selectedGiving)
        ratioDisplay.textContent = `Trade ratio: ${ratio}:1 (you give ${ratio}, you receive 1)`
        ratioDisplay.style.display = 'block'

        receiveContainer.innerHTML = RESOURCE_OPTIONS.filter((r) => r !== selectedGiving)
          .map(
            (r) =>
              `<button class="trade-res-btn" data-resource="${r}">
                <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
                <span class="res-name">${r}</span>
              </button>`,
          )
          .join('')

        receiveContainer.querySelectorAll('.trade-res-btn').forEach((rb) => {
          rb.addEventListener('click', () => {
            receiveContainer.querySelectorAll('.trade-res-btn').forEach((b) => b.classList.remove('selected'))
            rb.classList.add('selected')
            selectedReceiving = rb.dataset.resource
            confirmBtn.disabled = false
          })
        })

        receiveSection.style.display = 'block'
      })
    })

    confirmBtn.onclick = () => {
      if (!selectedGiving || !selectedReceiving) return
      modal.style.display = 'none'
      this.onAction({
        action_type: 'trade_with_bank',
        player_index: this.myPlayerIndex,
        giving: selectedGiving,
        receiving: selectedReceiving,
      })
    }
    cancelBtn.onclick = () => {
      modal.style.display = 'none'
    }

    modal.style.display = 'flex'
  }

  _getBankTradeRatio(resource) {
    if (!this.gameState || this.myPlayerIndex === null) return 4
    const player = this.gameState.players[this.myPlayerIndex]
    if (!player) return 4
    const ports = player.ports_owned || []
    if (ports.includes(resource)) return 2
    if (ports.includes('generic')) return 3
    return 4
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  _resourceTotal(resources) {
    return Object.values(resources || {}).reduce((a, b) => a + b, 0)
  }

  _showPlayerTradeDialog() {
    const modal = document.getElementById('player-trade-modal')
    if (!modal || !this.gameState || this.myPlayerIndex === null) return
    const player = this.gameState.players[this.myPlayerIndex]
    if (!player) return

    const offeringGrid = document.getElementById('player-trade-offering')
    const requestingGrid = document.getElementById('player-trade-requesting')
    const targetsContainer = document.getElementById('player-trade-targets')
    const confirmBtn = document.getElementById('player-trade-confirm')
    const cancelBtn = document.getElementById('player-trade-cancel')

    // Build stepper rows for offering (limited by player's hand)
    offeringGrid.innerHTML = RESOURCE_OPTIONS.map((r) => {
      const max = player.resources[r] || 0
      return `<div class="trade-stepper-row">
          <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
          <span class="res-name">${r}</span>
          <span class="res-hand">(${max})</span>
          <button class="stepper-btn" data-dir="-1" data-resource="${r}" data-side="offering">−</button>
          <span class="stepper-value" id="offering-${r}">0</span>
          <button class="stepper-btn" data-dir="1" data-resource="${r}" data-side="offering" ${max === 0 ? 'disabled' : ''}>+</button>
        </div>`
    }).join('')

    // Build stepper rows for requesting (no max)
    requestingGrid.innerHTML = RESOURCE_OPTIONS.map(
      (r) =>
        `<div class="trade-stepper-row">
          <span class="res-emoji">${RESOURCE_EMOJIS[r]}</span>
          <span class="res-name">${r}</span>
          <button class="stepper-btn" data-dir="-1" data-resource="${r}" data-side="requesting">−</button>
          <span class="stepper-value" id="requesting-${r}">0</span>
          <button class="stepper-btn" data-dir="1" data-resource="${r}" data-side="requesting">+</button>
        </div>`,
    ).join('')

    // Track values
    const offeringValues = Object.fromEntries(RESOURCE_OPTIONS.map((r) => [r, 0]))
    const requestingValues = Object.fromEntries(RESOURCE_OPTIONS.map((r) => [r, 0]))

    const updateConfirm = () => {
      const hasOffering = Object.values(offeringValues).some((v) => v > 0)
      const hasRequesting = Object.values(requestingValues).some((v) => v > 0)
      confirmBtn.disabled = !(hasOffering && hasRequesting)
    }

    const handleStepper = (btn) => {
      const res = btn.dataset.resource
      const side = btn.dataset.side
      const dir = parseInt(btn.dataset.dir, 10)
      const values = side === 'offering' ? offeringValues : requestingValues
      const max = side === 'offering' ? player.resources[res] || 0 : MAX_REQUESTING_AMOUNT
      const newVal = Math.max(0, Math.min(max, values[res] + dir))
      values[res] = newVal
      document.getElementById(`${side}-${res}`).textContent = newVal
      updateConfirm()
    }

    offeringGrid.querySelectorAll('.stepper-btn').forEach((btn) => btn.addEventListener('click', () => handleStepper(btn)))
    requestingGrid.querySelectorAll('.stepper-btn').forEach((btn) => btn.addEventListener('click', () => handleStepper(btn)))

    // Player targets
    const otherPlayers = this.gameState.players.filter((p) => p.player_index !== this.myPlayerIndex)
    targetsContainer.innerHTML =
      `<button class="trade-target-btn selected" data-target="all">🌐 All Players</button>` +
      otherPlayers
        .map(
          (p) =>
            `<button class="trade-target-btn" data-target="${p.player_index}">
              <span class="player-dot-sm" style="background:${escapeHtml(p.color)}"></span>
              ${escapeHtml(p.name)}
            </button>`,
        )
        .join('')

    targetsContainer.querySelectorAll('.trade-target-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        targetsContainer.querySelectorAll('.trade-target-btn').forEach((b) => b.classList.remove('selected'))
        btn.classList.add('selected')
      })
    })

    confirmBtn.disabled = true
    confirmBtn.onclick = () => {
      const offering = Object.fromEntries(Object.entries(offeringValues).filter(([, v]) => v > 0))
      const requesting = Object.fromEntries(Object.entries(requestingValues).filter(([, v]) => v > 0))
      const selectedTarget = targetsContainer.querySelector('.trade-target-btn.selected')
      const targetRaw = selectedTarget ? selectedTarget.dataset.target : 'all'
      const targetPlayer = targetRaw === 'all' ? null : parseInt(targetRaw, 10)
      modal.style.display = 'none'
      this.onAction({
        action_type: 'trade_offer',
        player_index: this.myPlayerIndex,
        offering,
        requesting,
        target_player: targetPlayer,
      })
    }
    cancelBtn.onclick = () => {
      modal.style.display = 'none'
    }

    modal.style.display = 'flex'
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
