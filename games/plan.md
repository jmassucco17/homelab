# Games Section — Implementation Plan

## Overview

This directory will host a games sub-site at `games.jamesmassucco.com`. The goals are:

1. **Warm-up games** – Build Snake and Pong to establish the tech stack and deployment pipeline.
2. **Main goal** – Build a Settlers of Catan emulator that two human players can play together, and that also supports computer (AI) opponents at multiple difficulty levels.

The plan is structured so that most phases can be executed in **parallel by independent agents**. Dependencies between workstreams are called out explicitly.

---

## Technology Choices

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.12, FastAPI, uvicorn | Consistent with existing services (blog, travel-site) |
| Real-time comms | FastAPI WebSockets | Built-in to FastAPI, no extra dependencies |
| Frontend | Vanilla HTML5 + CSS + JavaScript (Canvas API for game rendering) | No build toolchain needed; consistent with existing static-site approach |
| Templating | Jinja2 | Already in `requirements.txt` |
| Container | Docker + docker-compose | Consistent with all other services |
| Routing | Traefik (existing) | Add `games.jamesmassucco.com` label |

### Mobile / iOS compatibility

All chosen APIs are supported on iOS Safari and iOS Chrome (note: iOS Chrome uses the same WKWebView engine as Safari due to Apple App Store rules, so Safari compatibility implies iOS Chrome compatibility):

- **HTML5 Canvas** — fully supported on iOS Safari 9+ / Chrome for iOS
- **WebSockets** — fully supported on iOS Safari 8+ / Chrome for iOS
- **`requestAnimationFrame`** — fully supported on iOS Safari 6+ / Chrome for iOS
- **Touch events** (`touchstart`, `touchmove`, `touchend`) — the standard mechanism for touch input on iOS; keyboard controls are supplemented with on-screen touch controls for every game
- **`localStorage`** — fully supported for high-score persistence on iOS Safari (private browsing mode will limit storage but not break the game)
- **Viewport meta tag** (`<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">`) — required in every template to prevent double-tap zoom and ensure correct canvas sizing on high-DPI Retina displays
- **`devicePixelRatio` scaling** — canvas drawing surfaces must be scaled by `window.devicePixelRatio` (typically 2–3× on iPhone) to avoid blurry rendering; CSS size and canvas pixel size must be set independently

One known iOS Safari caveat: **WebSockets over HTTP are blocked**; connections must use `wss://` (HTTPS). Since the site already runs behind Traefik with Let's Encrypt certificates, this is already satisfied.

---

## Phase 0 — Infrastructure (parallel with all other phases)

**Agent: infra-agent**
No other phase can be deployed until this is done, but development of game logic and UI can proceed locally in parallel.

- [ ] Create `games/Dockerfile` — mirror `blog/Dockerfile`, serving from `games/app/`
- [ ] Create `games/docker-compose.yml` — Traefik labels for `games.jamesmassucco.com`, port 8000, healthcheck
- [ ] Create `games/start.sh` — mirror `blog/start.sh`
- [ ] Update `scripts/start_all.sh` — add `"games"` to the `PROJECTS` array
- [ ] Update `networking/docker-compose.yml` — add DNS/certificate entry for `games.jamesmassucco.com` (follow pattern of other sub-domains in that file)
- [ ] Update `.github/dependabot.yml` — add Docker entry for `/games` directory
- [ ] Create `games/app/` skeleton — FastAPI app entry point `games/app/main.py` with a `/health` endpoint and a root route that renders `index.html`
- [ ] Create `games/app/templates/base.html` — shared HTML shell (nav bar linking to Snake, Pong, and Catan; link to shared-assets CSS if applicable)
- [ ] Create `games/app/static/` — directory for per-game JS/CSS files

---

## Phase 1 — Snake (self-contained; no backend state needed)

**Agent: snake-agent** — depends only on Phase 0 skeleton (can develop against a local static HTML file before Phase 0 is complete)

### 1a — Game logic (`games/app/static/snake/snake.js`)
- [ ] Implement core game loop using `requestAnimationFrame`
- [ ] Grid-based snake movement, wall and self-collision detection
- [ ] Food spawning and score tracking
- [ ] Keyboard controls (arrow keys / WASD)
- [ ] Game-over screen with restart button
- [ ] Speed increase as score grows

### 1b — UI/template (`games/app/templates/snake.html`)
- [ ] HTML Canvas element sized to game grid
- [ ] Score display, high-score stored in `localStorage`
- [ ] Mobile-friendly touch swipe controls
- [ ] Responsive CSS

### 1c — Backend route (`games/app/routers/snake.py`)
- [ ] `GET /snake` — renders `snake.html` template
- [ ] Register router in `main.py`

---

## Phase 2 — Pong (self-contained; no backend state needed)

**Agent: pong-agent** — runs fully in parallel with Phase 1

### 2a — Game logic (`games/app/static/pong/pong.js`)
- [ ] Canvas-based rendering (paddles, ball, score)
- [ ] Physics: ball velocity, bouncing off walls and paddles, angle variation based on hit position
- [ ] Single-player mode: right paddle controlled by simple AI (tracks ball Y position with a configurable speed cap)
- [ ] Two-player local mode: left paddle = W/S keys, right paddle = Up/Down arrows
- [ ] Mobile two-player mode: left paddle = left-side touch drag, right paddle = right-side touch drag (two-thumb play)
- [ ] Game-over at first player to reach 7 points; rematch button

### 2b — UI/template (`games/app/templates/pong.html`)
- [ ] Mode selection screen (1P vs 2P)
- [ ] Responsive canvas; pause on tab blur

### 2c — Backend route (`games/app/routers/pong.py`)
- [ ] `GET /pong` — renders `pong.html` template
- [ ] Register router in `main.py`

---

## Phase 3 — Catan: Architecture & Shared Contracts

**Agent: catan-arch-agent** — must complete before Phases 4–8 begin; can run in parallel with Phases 1 and 2

This phase produces the shared data models and API contracts that all other Catan agents depend on. No runnable game code is produced here, but it unblocks all parallel Catan workstreams.

- [ ] **Board model** (`games/app/catan/models/board.py`)
  - Hexagonal grid representation (cube coordinates)
  - Tile types: forest, pasture, fields, hills, mountains, desert
  - Number tokens (2–12, excluding 7)
  - Port locations and types (3:1 and 2:1)
  - Vertex and edge data structures (for settlements/cities/roads)
  - Robber position
- [ ] **Player model** (`games/app/catan/models/player.py`)
  - Resources (wood, brick, wheat, sheep, ore)
  - Development card hand
  - Build inventory (settlements, cities, roads remaining)
  - Victory points
  - Ports owned
- [ ] **Game state model** (`games/app/catan/models/game_state.py`)
  - Player list and turn order
  - Current phase (setup, main, ended)
  - Current turn: player index, roll value, pending actions
  - Longest road / largest army tracking
  - Dice roll history
- [ ] **Action schemas** (`games/app/catan/models/actions.py`)
  - Pydantic models for every legal action: `PlaceSettlement`, `PlaceRoad`, `PlaceCity`, `RollDice`, `BuildDevCard`, `PlayKnight`, `PlayRoadBuilding`, `PlayYearOfPlenty`, `PlayMonopoly`, `TradeOffer`, `TradeWithBank`, `TradeWithPort`, `EndTurn`, `MoveRobber`, `StealResource`
  - `ActionResult` model (success, updated state, error message)
- [ ] **WebSocket message schemas** (`games/app/catan/models/ws_messages.py`)
  - Client→Server: `JoinGame`, `SubmitAction`, `RequestUndo` (setup only)
  - Server→Client: `GameStateUpdate`, `ErrorMessage`, `PlayerJoined`, `GameStarted`, `GameOver`
- [ ] **Board generation algorithm** (`games/app/catan/board_generator.py`)
  - Standard random layout (shuffle tiles and number tokens per Catan rules)
  - Optional: balanced placement algorithm (no adjacent red numbers)
  - Return serializable `Board` instance
- [ ] **Serialization helpers** (`games/app/catan/models/serializers.py`)
  - JSON-serializable forms of all models (for WebSocket transport and persistence)

---

## Phase 4 — Catan: Game Engine (backend)

**Agent: catan-engine-agent** — depends on Phase 3 contracts; runs in parallel with Phases 5–8

- [ ] **Rules engine** (`games/app/catan/engine/rules.py`)
  - `get_legal_actions(game_state, player_index) -> list[Action]`
  - Setup phase: initial placement rules (no adjacency), road adjacent to own settlement
  - Main phase: build cost checks, placement validity (vertex/edge ownership, connectivity)
  - Robber rules: must move on 7 or knight, must steal from adjacent player if possible
  - Longest road calculation (DFS over edge graph)
  - Largest army tracking
  - Victory condition check (≥10 VP)
- [ ] **Action processor** (`games/app/catan/engine/processor.py`)
  - `apply_action(game_state, action) -> ActionResult`
  - Pure function (no side effects); returns new `GameState`
  - Handles all action types defined in Phase 3
  - Resource bank validation (finite resource cards)
- [ ] **Turn manager** (`games/app/catan/engine/turn_manager.py`)
  - Setup phase order (1→2→…→N→N→…→1 snake-draft)
  - Main phase turn cycling
  - Dice roll → distribute resources → check robber → await player actions
- [ ] **Unit tests** (`games/tests/catan/test_engine.py`)
  - Legal action generation edge cases (can't build where occupied, etc.)
  - Resource distribution on roll (including 7)
  - Robber placement and stealing
  - Longest road and largest army transitions
  - Victory condition detection

---

## Phase 5 — Catan: Multiplayer Backend (WebSocket server)

**Agent: catan-server-agent** — depends on Phase 3 contracts; runs in parallel with Phases 4, 6, 7, 8

- [ ] **Room manager** (`games/app/catan/server/room_manager.py`)
  - Create/join game rooms (4-character room codes)
  - Store active `GameState` per room (in-memory; persistence is Phase 9 stretch)
  - Track connected WebSocket clients per room
  - Handle disconnection / reconnection (hold player slot for 60 s)
- [ ] **WebSocket handler** (`games/app/catan/server/ws_handler.py`)
  - `GET /catan/ws/{room_code}/{player_name}` WebSocket endpoint
  - Authenticate player by name (first come, first served up to 4 players)
  - Receive `SubmitAction` → validate via rules engine → apply via processor → broadcast `GameStateUpdate` to all clients in room
  - Broadcast `ErrorMessage` to acting player on invalid action
  - Handle `JoinGame`, `GameStarted` lifecycle messages
- [ ] **HTTP routes** (`games/app/routers/catan.py`)
  - `GET /catan` — lobby/landing page
  - `POST /catan/rooms` — create a new room, return room code
  - `GET /catan/rooms/{room_code}` — room status (player count, game phase)
  - Register router in `main.py`
- [ ] **Integration tests** (`games/tests/catan/test_ws.py`)
  - Two-client WebSocket flow: create room → join → start game → take turns → win

---

## Phase 6 — Catan: Frontend Rendering

**Agent: catan-frontend-agent** — depends on Phase 3 WS message schemas; runs in parallel with Phases 4, 5, 7, 8

- [ ] **Board renderer** (`games/app/static/catan/board.js`)
  - SVG or Canvas rendering of hexagonal board
  - Draw tiles with terrain icons/colors, number tokens
  - Highlight valid placement vertices/edges (fed from server's legal actions)
  - Animate resource collection on dice roll
  - Show robber piece on active hex
  - Responsive sizing; scale canvas by `window.devicePixelRatio` for sharp Retina rendering on iPhone
  - Touch event handling for tile/vertex/edge selection (`touchstart` / `touchend`); tap targets sized ≥44×44 px per Apple HIG
  - Pinch-to-zoom and pan on mobile for the full board view
- [ ] **UI components** (`games/app/static/catan/ui.js`)
  - Player hand panel (resource counts, dev cards)
  - Build menu (road, settlement, city, dev card) with cost display; grayed out when insufficient resources
  - Trade panel (bank trade, port trade, player-to-player offer)
  - Dice roll animation
  - Victory point tracker for all players
  - End-turn button; dev card play buttons
- [ ] **WebSocket client** (`games/app/static/catan/ws_client.js`)
  - Connect to `/catan/ws/{room_code}/{player_name}`
  - Send `SubmitAction` on player interaction
  - Receive `GameStateUpdate` → reconcile local state → re-render
  - Display `ErrorMessage` as toast notification
  - Handle `GameStarted` / `GameOver` screens
- [ ] **Lobby UI** (`games/app/templates/catan_lobby.html` + `catan.js`)
  - Create room / join by room code form
  - Waiting room showing joined players; "Start Game" button for room creator (≥2 players)
  - Add AI player button (triggers Phase 8 AI slot)
- [ ] **Game template** (`games/app/templates/catan_game.html`)
  - Canvas/SVG area + side panels
  - Chat/log sidebar showing action history

---

## Phase 7 — Catan: Trading System (backend extension)

**Agent: catan-trade-agent** — depends on Phase 4 engine; runs in parallel with Phases 5, 6, 8

The trade system is complex enough to warrant its own workstream.

- [ ] **Trade logic** (`games/app/catan/engine/trade.py`)
  - Bank trade: 4:1 always; 3:1 with generic harbor; 2:1 with specific harbor
  - Validate player has enough resources
  - Player-to-player trade offer/accept/reject lifecycle (offer state machine)
  - Domestic trade restricted to active player's turn
- [ ] **Trade action types** — extend Phase 3 `actions.py` if needed:
  - `ProposeTrade(offering: Resources, requesting: Resources, target_player: int | None)`
  - `AcceptTrade(trade_id: str)`, `RejectTrade(trade_id: str)`, `CancelTrade(trade_id: str)`
- [ ] **WebSocket messages for trade** — extend Phase 3 `ws_messages.py`:
  - `TradeProposed`, `TradeAccepted`, `TradeRejected`, `TradeCancelled`
- [ ] **Tests** (`games/tests/catan/test_trade.py`)
  - Bank trade calculations (all harbor types)
  - Player trade happy path and rejection
  - Can't trade resources you don't have

---

## Phase 8 — Catan: AI Players

**Agent: catan-ai-agent** — depends on Phase 4 engine; runs in parallel with Phases 5, 6, 7

- [ ] **AI interface** (`games/app/catan/ai/base.py`)
  - Abstract `CatanAI` class with `choose_action(game_state, player_index, legal_actions) -> Action`
  - Pluggable: multiple difficulty levels implement the same interface
- [ ] **Rule-based AI — Easy** (`games/app/catan/ai/easy.py`)
  - Always picks a random legal action
  - Used to sanity-test game-complete simulations
- [ ] **Rule-based AI — Medium** (`games/app/catan/ai/medium.py`)
  - Prioritizes building (settlement > road > city > dev card) using a simple heuristic priority queue
  - Prefers settlement spots with highest pip count and resource diversity
  - Trades with bank when stuck (4:1 if no port)
  - Plays knight when holding it and score is close
- [ ] **Rule-based AI — Hard** (`games/app/catan/ai/hard.py`)
  - Settlement placement: maximize expected resource income + port access using pip-count + resource-distribution scoring
  - Longest road strategy: tracks road count and chases the bonus when within reach
  - Largest army strategy: tracks knight counts across players
  - Adaptive trading: uses ports strategically; counter-offers player trades
  - Robber placement: targets the leader; avoids self-harm
- [ ] **AI driver** (`games/app/catan/ai/driver.py`)
  - Runs AI turn asynchronously in the server (1–3 s simulated delay for UX)
  - Invoked by `ws_handler.py` when it is an AI player's turn
- [ ] **Simulation runner** (`games/tests/catan/simulate.py`)
  - Run 1000 full games AI-vs-AI to verify no infinite loops, check win-rate distribution
  - Output: average game length, win rates by seat position

---

## Phase 9 — Polish & Stretch Goals (post-MVP)

These items are lower priority and can be picked up after the MVP is playable.

- [ ] **Persistence** — store completed game records in SQLite (using `sqlmodel`, already in `requirements.txt`) so scores and history are preserved across container restarts
- [ ] **Spectator mode** — read-only WebSocket connection to watch a game in progress
- [ ] **Reconnection** — persist game state to disk so players can rejoin after a network drop
- [ ] **Victory point cards** — currently treated like any dev card; add proper reveal-on-win handling
- [ ] **Mobile UI polish** — touch-friendly drag-and-drop placement on the Catan board
- [ ] **Sound effects** — dice roll, resource collection, building placement audio cues
- [ ] **Undo in setup phase** — allow players to take back initial placements before the main game begins
- [ ] **Custom board** — UI to manually place tiles for a custom game

---

## Dependency Graph Summary

```
Phase 0 (Infra)
    │
    ├── Phase 1 (Snake)          ← independent
    ├── Phase 2 (Pong)           ← independent
    │
    └── Phase 3 (Catan Arch)    ← independent of Phases 1–2
            │
            ├── Phase 4 (Engine)     ─┐
            ├── Phase 5 (WS Server)   ├── all parallel
            ├── Phase 6 (Frontend)    │
            ├── Phase 7 (Trading)    ─┤  (7 depends on 4)
            └── Phase 8 (AI)         ─┘  (8 depends on 4)
                    │
                    └── Phase 9 (Polish)
```

**Minimum viable parallelism:** Assign five agents simultaneously — one each for Phases 0, 1, 2, 3, and then split Phases 4–8 across five more agents once Phase 3 is complete.

---

## File Tree (target state)

```
games/
├── plan.md                          # this file
├── Dockerfile
├── docker-compose.yml
├── start.sh
└── app/
    ├── main.py                      # FastAPI app, registers all routers
    ├── routers/
    │   ├── snake.py
    │   ├── pong.py
    │   └── catan.py
    ├── templates/
    │   ├── base.html
    │   ├── index.html               # games landing page
    │   ├── snake.html
    │   ├── pong.html
    │   ├── catan_lobby.html
    │   └── catan_game.html
    ├── static/
    │   ├── snake/
    │   │   └── snake.js
    │   ├── pong/
    │   │   └── pong.js
    │   └── catan/
    │       ├── board.js
    │       ├── ui.js
    │       ├── ws_client.js
    │       └── catan.js
    ├── catan/
    │   ├── models/
    │   │   ├── board.py
    │   │   ├── player.py
    │   │   ├── game_state.py
    │   │   ├── actions.py
    │   │   ├── ws_messages.py
    │   │   └── serializers.py
    │   ├── board_generator.py
    │   ├── engine/
    │   │   ├── rules.py
    │   │   ├── processor.py
    │   │   ├── turn_manager.py
    │   │   └── trade.py
    │   ├── server/
    │   │   ├── room_manager.py
    │   │   └── ws_handler.py
    │   └── ai/
    │       ├── base.py
    │       ├── easy.py
    │       ├── medium.py
    │       ├── hard.py
    │       └── driver.py
    └── tests/
        └── catan/
            ├── test_engine.py
            ├── test_ws.py
            ├── test_trade.py
            └── simulate.py
```
