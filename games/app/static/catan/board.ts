/**
 * Catan board renderer — Canvas-based hexagonal board rendering.
 *
 * Features:
 *  - Flat-top hexagonal tile layout using cube coordinates
 *  - Terrain colours and emoji icons per tile type
 *  - Number token circles with pip indicators (red for 6/8)
 *  - Vertex (settlement/city) and edge (road) rendering
 *  - Legal-placement highlights for vertices, edges and tiles
 *  - Robber piece on active tile
 *  - Port markers on coastal edges
 *  - Mouse pan (drag) and scroll-wheel zoom
 *  - Touch pan (single finger) and pinch-to-zoom
 *  - Tap/click hit-detection for vertices, edges and tiles
 *  - devicePixelRatio canvas scaling for sharp Retina rendering
 *  - ResizeObserver so the canvas fills its parent automatically
 */

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface Point {
  x: number
  y: number
}

interface TileCoord {
  q: number
  r: number
  s: number
}

interface Building {
  player_index: number
  building_type: string
}

interface Road {
  player_index: number
}

export interface BoardVertex {
  vertex_id: number
  building: Building | null
}

export interface BoardEdge {
  edge_id: number
  vertex_ids: [number, number]
  road: Road | null
}

interface BoardPort {
  port_type: string
  vertex_ids: [number, number]
}

interface BoardTile {
  tile_type: string
  number_token: number | null
  coord: TileCoord
}

export interface BoardData {
  tiles: BoardTile[]
  vertices: BoardVertex[]
  edges: BoardEdge[]
  ports: BoardPort[]
  robber_tile_index: number
}

// Type for objects that look like mouse click events (used so touch events can call _handleClick)
type ClickLike = { clientX: number; clientY: number }

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

/** Six neighbour directions in cube coordinate space (matches board_generator.py). */
const HEX_DIRS: number[][] = [
  [1, -1, 0],
  [1, 0, -1],
  [0, 1, -1],
  [-1, 1, 0],
  [-1, 0, 1],
  [0, -1, 1],
]

/**
 * Convert flat-top cube coordinates to pixel centre.
 */
function cubeToPixel(q: number, r: number, size: number): Point {
  return {
    x: size * 1.5 * q,
    y: size * (Math.sqrt(3) * 0.5 * q + Math.sqrt(3) * r),
  }
}

/**
 * Return the pixel position of flat-top hex corner i (0 = right, clockwise).
 */
function hexCorner(cx: number, cy: number, size: number, i: number): Point {
  const rad = (Math.PI / 180) * 60 * i
  return { x: cx + size * Math.cos(rad), y: cy + size * Math.sin(rad) }
}

/**
 * Canonical sorted string key for a vertex defined by three cube-coord arrays.
 * Mirrors the frozenset key used in board_generator.py.
 */
function vertexKey(c0: number[], c1: number[], c2: number[]): string {
  return [c0, c1, c2]
    .map((c) => c.join(','))
    .sort()
    .join('|')
}

// ---------------------------------------------------------------------------
// Visual constants
// ---------------------------------------------------------------------------

const TILE_COLORS: Record<string, string> = {
  forest: '#2d6a2f',
  pasture: '#90d14e',
  fields: '#e8c43e',
  hills: '#b84d26',
  mountains: '#7a7a7a',
  desert: '#e3d0a0',
}

const TILE_EMOJIS: Record<string, string> = {
  forest: '🌲',
  pasture: '🐑',
  fields: '🌾',
  hills: '🧱',
  mountains: '⛰️',
  desert: '🏜️',
}

const PORT_COLORS: Record<string, string> = {
  generic: '#7a5c14',
  wood: '#2d6a2f',
  brick: '#b84d26',
  wheat: '#c49a00',
  sheep: '#5a9e2a',
  ore: '#555',
}

const PORT_LABELS: Record<string, string> = {
  generic: '3:1',
  wood: '2:1🌲',
  brick: '2:1🧱',
  wheat: '2:1🌾',
  sheep: '2:1🐑',
  ore: '2:1⛰',
}

const PIP_COUNTS: { [key: number]: number } = {
  2: 1,
  3: 2,
  4: 3,
  5: 4,
  6: 5,
  8: 5,
  9: 4,
  10: 3,
  11: 2,
  12: 1,
}
const RED_NUMBERS = new Set([6, 8])

// ---------------------------------------------------------------------------
// Renderer class
// ---------------------------------------------------------------------------

export class CatanBoardRenderer {
  canvas: HTMLCanvasElement
  ctx: CanvasRenderingContext2D
  dpr: number
  hexSize: number

  board: BoardData | null

  // Computed geometry (populated by _computeGeometry)
  vertexPixels: Record<number, Point>
  edgePixels: Record<number, Point>
  tileCenters: Point[]

  // Interactive state
  legalVertexIds: Set<number>
  legalEdgeIds: Set<number>
  legalTileIndices: Set<number>
  robberTileIndex: number
  playerColors: string[]

  // Interaction callbacks
  onVertexClick: ((vertexId: number) => void) | null
  onEdgeClick: ((edgeId: number) => void) | null
  onTileClick: ((tileIndex: number) => void) | null

  // Pan / zoom
  panX: number
  panY: number
  zoom: number

  // Internal interaction tracking
  _isPanning: boolean
  _lastPanPos: Point | null
  _mouseStartPos: Point | null
  _mouseMoved: boolean
  _touchStartPos: Point | null
  _touchMoved: boolean
  _pinchStartDist: number | null

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d') as CanvasRenderingContext2D
    this.dpr = window.devicePixelRatio || 1
    this.hexSize = 60

    this.board = null

    this.vertexPixels = {}
    this.edgePixels = {}
    this.tileCenters = []

    this.legalVertexIds = new Set()
    this.legalEdgeIds = new Set()
    this.legalTileIndices = new Set()
    this.robberTileIndex = 0
    this.playerColors = ['#e63946', '#457b9d', '#2a9d8f', '#e9c46a']

    this.onVertexClick = null
    this.onEdgeClick = null
    this.onTileClick = null

    this.panX = 0
    this.panY = 0
    this.zoom = 1

    this._isPanning = false
    this._lastPanPos = null
    this._mouseStartPos = null
    this._mouseMoved = false
    this._touchStartPos = null
    this._touchMoved = false
    this._pinchStartDist = null

    this._initEvents()
    this._initResize()
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /** Set initial board data and compute geometry. */
  setBoard(boardData: BoardData): void {
    this.board = boardData
    this.robberTileIndex = boardData.robber_tile_index
    this._computeGeometry()
    this._fitToCanvas()
    this.render()
  }

  /** Update board data without resetting pan/zoom (called on every game-state update). */
  updateBoard(boardData: BoardData): void {
    this.board = boardData
    this.robberTileIndex = boardData.robber_tile_index
    this.render()
  }

  /** Highlight valid settlement/city placement vertices. */
  setLegalVertices(ids: number[]): void {
    this.legalVertexIds = new Set(ids)
    this.render()
  }

  /** Highlight valid road placement edges. */
  setLegalEdges(ids: number[]): void {
    this.legalEdgeIds = new Set(ids)
    this.render()
  }

  /** Highlight valid robber placement tiles. */
  setLegalTiles(indices: number[]): void {
    this.legalTileIndices = new Set(indices)
    this.render()
  }

  /** Set player CSS colours (indexed by player_index). */
  setPlayerColors(colors: string[]): void {
    this.playerColors = colors
    this.render()
  }

  // -------------------------------------------------------------------------
  // Geometry computation
  // -------------------------------------------------------------------------

  _computeGeometry(): void {
    if (!this.board) return
    const positions = this.board.tiles.map((t): [number, number, number] => [
      t.coord.q,
      t.coord.r,
      t.coord.s,
    ])

    // ---- Assign vertex IDs (mirrors board_generator.py _build_grid_structure) ----
    const vKeyToId: { [key: string]: number | undefined } = {}
    for (const [q, r, s] of positions) {
      for (let i = 0; i < 6; i++) {
        const d0 = HEX_DIRS[i]
        const d1 = HEX_DIRS[(i + 1) % 6]
        const n0 = [q + d0[0], r + d0[1], s + d0[2]]
        const n1 = [q + d1[0], r + d1[1], s + d1[2]]
        const vk = vertexKey([q, r, s], n0, n1)
        if (!(vk in vKeyToId)) {
          vKeyToId[vk] = Object.keys(vKeyToId).length
        }
      }
    }

    // ---- Tile centres ----
    this.tileCenters = positions.map(([q, r]) => cubeToPixel(q, r, this.hexSize))

    // ---- Vertex pixel positions ----
    this.vertexPixels = {}
    for (let ti = 0; ti < positions.length; ti++) {
      const [q, r, s] = positions[ti]
      const center = this.tileCenters[ti]
      for (let i = 0; i < 6; i++) {
        const corner = hexCorner(center.x, center.y, this.hexSize, i)
        const d0 = HEX_DIRS[i]
        const d1 = HEX_DIRS[(i + 1) % 6]
        const n0 = [q + d0[0], r + d0[1], s + d0[2]]
        const n1 = [q + d1[0], r + d1[1], s + d1[2]]
        const vk = vertexKey([q, r, s], n0, n1)
        const vid = vKeyToId[vk]
        if (vid !== undefined && !(vid in this.vertexPixels)) {
          this.vertexPixels[vid] = corner
        }
      }
    }

    // ---- Edge pixel positions (midpoint of two endpoint vertices) ----
    this.edgePixels = {}
    for (const edge of this.board.edges) {
      const p0 = this.vertexPixels[edge.vertex_ids[0]]
      const p1 = this.vertexPixels[edge.vertex_ids[1]]
      if (p0 && p1) {
        this.edgePixels[edge.edge_id] = {
          x: (p0.x + p1.x) / 2,
          y: (p0.y + p1.y) / 2,
        }
      }
    }
  }

  /** Scale and centre the board to fill the canvas. */
  _fitToCanvas(): void {
    if (!this.board) return
    const xs = this.tileCenters.map((c) => c.x)
    const ys = this.tileCenters.map((c) => c.y)
    const minX = Math.min(...xs) - this.hexSize * 1.2
    const maxX = Math.max(...xs) + this.hexSize * 1.2
    const minY = Math.min(...ys) - this.hexSize * 1.2
    const maxY = Math.max(...ys) + this.hexSize * 1.2
    const boardW = maxX - minX
    const boardH = maxY - minY
    const cssW = this.canvas.clientWidth || 600
    const cssH = this.canvas.clientHeight || 600
    this.zoom = Math.min(cssW / boardW, cssH / boardH) * 0.92
    this.panX = (cssW - boardW * this.zoom) / 2 - minX * this.zoom
    this.panY = (cssH - boardH * this.zoom) / 2 - minY * this.zoom
  }

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  render(): void {
    if (!this.board) return
    const { canvas, ctx, dpr, zoom, panX, panY } = this

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.save()
    ctx.scale(dpr, dpr)
    ctx.translate(panX, panY)
    ctx.scale(zoom, zoom)

    for (let ti = 0; ti < this.board.tiles.length; ti++) {
      this._drawTile(ti)
    }

    for (const edge of this.board.edges) {
      this._drawEdge(edge)
    }

    for (const vertex of this.board.vertices) {
      this._drawVertex(vertex)
    }

    this._drawPorts()

    ctx.restore()
  }

  _drawTile(tileIndex: number): void {
    if (!this.board) return
    const board = this.board
    const tile = board.tiles[tileIndex]
    const center = this.tileCenters[tileIndex]
    const { ctx, hexSize } = this
    const innerSize = hexSize - 2 // slight gap between tiles

    const isLegal = this.legalTileIndices.has(tileIndex)
    const baseColor = TILE_COLORS[tile.tile_type] || '#ccc'

    // Hex fill
    ctx.beginPath()
    for (let i = 0; i < 6; i++) {
      const c = hexCorner(center.x, center.y, innerSize, i)
      if (i === 0) ctx.moveTo(c.x, c.y)
      else ctx.lineTo(c.x, c.y)
    }
    ctx.closePath()
    ctx.fillStyle = isLegal ? this._lighten(baseColor, 0.35) : baseColor
    ctx.fill()
    ctx.strokeStyle = isLegal ? '#ffcc00' : '#44443a'
    ctx.lineWidth = isLegal ? 3 / this.zoom : 1 / this.zoom
    ctx.stroke()

    // Terrain emoji (above centre so number token fits below)
    if (tile.tile_type !== 'desert') {
      ctx.font = `${hexSize * 0.38}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(TILE_EMOJIS[tile.tile_type] || '', center.x, center.y - hexSize * 0.3)
    }

    // Number token
    if (tile.number_token !== null && tile.number_token !== undefined) {
      const isRed = RED_NUMBERS.has(tile.number_token)
      const tokenR = hexSize * 0.26

      ctx.beginPath()
      ctx.arc(center.x, center.y + hexSize * 0.15, tokenR, 0, Math.PI * 2)
      ctx.fillStyle = '#f5e6c0'
      ctx.fill()
      ctx.strokeStyle = '#aaa'
      ctx.lineWidth = 1 / this.zoom
      ctx.stroke()

      ctx.fillStyle = isRed ? '#c00' : '#222'
      ctx.font = `bold ${hexSize * 0.26}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(String(tile.number_token), center.x, center.y + hexSize * 0.13)

      // Pip dots below number
      const pips = PIP_COUNTS[tile.number_token] || 0
      const pipY = center.y + hexSize * 0.15 + tokenR * 0.62
      const pipSpacing = tokenR * 0.36
      const pipStartX = center.x - ((pips - 1) / 2) * pipSpacing
      ctx.fillStyle = isRed ? '#c00' : '#555'
      for (let p = 0; p < pips; p++) {
        ctx.beginPath()
        ctx.arc(pipStartX + p * pipSpacing, pipY, tokenR * 0.1, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    // Robber
    if (tileIndex === this.robberTileIndex) {
      ctx.font = `${hexSize * 0.52}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('🥷', center.x, center.y + hexSize * 0.18)
    }
  }

  _drawVertex(vertex: BoardVertex): void {
    const pos = this.vertexPixels[vertex.vertex_id]
    if (!pos) return
    const { ctx, hexSize } = this

    if (vertex.building) {
      const color = this.playerColors[vertex.building.player_index] || '#888'
      const isCity = vertex.building.building_type === 'city'
      const r = hexSize * (isCity ? 0.22 : 0.15)

      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2 / this.zoom
      ctx.stroke()

      if (isCity) {
        ctx.beginPath()
        ctx.arc(pos.x, pos.y, r * 0.45, 0, Math.PI * 2)
        ctx.fillStyle = '#fff'
        ctx.fill()
      }
    } else if (this.legalVertexIds.has(vertex.vertex_id)) {
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, hexSize * 0.13, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(255, 210, 0, 0.75)'
      ctx.fill()
      ctx.strokeStyle = '#ffcc00'
      ctx.lineWidth = 2 / this.zoom
      ctx.stroke()
    }
  }

  _drawEdge(edge: BoardEdge): void {
    const p0 = this.vertexPixels[edge.vertex_ids[0]]
    const p1 = this.vertexPixels[edge.vertex_ids[1]]
    if (!p0 || !p1) return
    const { ctx, hexSize } = this

    if (edge.road) {
      const color = this.playerColors[edge.road.player_index] || '#888'
      ctx.beginPath()
      ctx.moveTo(p0.x, p0.y)
      ctx.lineTo(p1.x, p1.y)
      ctx.strokeStyle = color
      ctx.lineWidth = hexSize * 0.11
      ctx.lineCap = 'round'
      ctx.stroke()
    } else if (this.legalEdgeIds.has(edge.edge_id)) {
      ctx.beginPath()
      ctx.moveTo(p0.x, p0.y)
      ctx.lineTo(p1.x, p1.y)
      ctx.strokeStyle = 'rgba(255, 210, 0, 0.8)'
      ctx.lineWidth = hexSize * 0.09
      ctx.lineCap = 'round'
      ctx.stroke()
    }
  }

  _drawPorts(): void {
    if (!this.board) return
    const { ctx, hexSize } = this
    const board = this.board
    if (!board.ports) return

    for (const port of board.ports) {
      const p0 = this.vertexPixels[port.vertex_ids[0]]
      const p1 = this.vertexPixels[port.vertex_ids[1]]
      if (!p0 || !p1) continue

      const mx = (p0.x + p1.x) / 2
      const my = (p0.y + p1.y) / 2
      const r = hexSize * 0.2

      ctx.beginPath()
      ctx.arc(mx, my, r, 0, Math.PI * 2)
      ctx.fillStyle = PORT_COLORS[port.port_type] || '#7a5c14'
      ctx.globalAlpha = 0.88
      ctx.fill()
      ctx.globalAlpha = 1

      ctx.fillStyle = '#fff'
      ctx.font = `bold ${hexSize * 0.16}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(PORT_LABELS[port.port_type] || '?', mx, my)
    }
  }

  // -------------------------------------------------------------------------
  // Input handling
  // -------------------------------------------------------------------------

  _initEvents(): void {
    const c = this.canvas

    c.addEventListener('click', (e) => this._handleClick(e))
    c.addEventListener('mousedown', (e) => this._onMouseDown(e))
    c.addEventListener('mousemove', (e) => this._onMouseMove(e))
    c.addEventListener('mouseup', () => {
      this._isPanning = false
    })
    c.addEventListener('mouseleave', () => {
      this._isPanning = false
    })
    c.addEventListener('wheel', (e) => this._onWheel(e), { passive: false })

    c.addEventListener('touchstart', (e) => this._onTouchStart(e), { passive: false })
    c.addEventListener('touchmove', (e) => this._onTouchMove(e), { passive: false })
    c.addEventListener('touchend', (e) => this._onTouchEnd(e))
  }

  /** Convert a CSS-pixel canvas position to logical board coordinates. */
  _boardPos(canvasX: number, canvasY: number): Point {
    return {
      x: (canvasX - this.panX) / this.zoom,
      y: (canvasY - this.panY) / this.zoom,
    }
  }

  _handleClick(e: ClickLike): void {
    if (this._mouseMoved) {
      this._mouseMoved = false
      return
    }
    if (!this.board) return

    const rect = this.canvas.getBoundingClientRect()
    const pos = this._boardPos(e.clientX - rect.left, e.clientY - rect.top)
    const hitR = this.hexSize * 0.22

    // Vertices (highest priority)
    for (const [vid, vpos] of Object.entries(this.vertexPixels)) {
      const dx = pos.x - vpos.x
      const dy = pos.y - vpos.y
      if (Math.sqrt(dx * dx + dy * dy) < hitR) {
        if (this.onVertexClick) this.onVertexClick(Number(vid))
        return
      }
    }

    // Edges
    for (const edge of this.board.edges) {
      const ep = this.edgePixels[edge.edge_id]
      if (!ep) continue
      const dx = pos.x - ep.x
      const dy = pos.y - ep.y
      if (Math.sqrt(dx * dx + dy * dy) < hitR) {
        if (this.onEdgeClick) this.onEdgeClick(edge.edge_id)
        return
      }
    }

    // Tiles (lowest priority — robber placement)
    for (let ti = 0; ti < this.board.tiles.length; ti++) {
      const tc = this.tileCenters[ti]
      const dx = pos.x - tc.x
      const dy = pos.y - tc.y
      if (Math.sqrt(dx * dx + dy * dy) < this.hexSize * 0.8) {
        if (this.legalTileIndices.has(ti) && this.onTileClick) {
          this.onTileClick(ti)
        }
        return
      }
    }
  }

  _onMouseDown(e: MouseEvent): void {
    this._isPanning = true
    this._mouseMoved = false
    this._lastPanPos = { x: e.clientX, y: e.clientY }
    this._mouseStartPos = { x: e.clientX, y: e.clientY }
  }

  _onMouseMove(e: MouseEvent): void {
    if (!this._isPanning || !this._lastPanPos || !this._mouseStartPos) return
    const dx = e.clientX - this._lastPanPos.x
    const dy = e.clientY - this._lastPanPos.y
    const totalDX = e.clientX - this._mouseStartPos.x
    const totalDY = e.clientY - this._mouseStartPos.y
    if (Math.sqrt(totalDX * totalDX + totalDY * totalDY) > 4) this._mouseMoved = true
    this.panX += dx
    this.panY += dy
    this._lastPanPos = { x: e.clientX, y: e.clientY }
    this.render()
  }

  _onWheel(e: WheelEvent): void {
    e.preventDefault()
    const rect = this.canvas.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    this._zoomAround(cx, cy, e.deltaY > 0 ? 0.9 : 1.1)
  }

  _onTouchStart(e: TouchEvent): void {
    if (e.touches.length === 1) {
      this._touchMoved = false
      this._touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY }
      this._lastPanPos = { x: e.touches[0].clientX, y: e.touches[0].clientY }
      this._pinchStartDist = null
    } else if (e.touches.length === 2) {
      this._pinchStartDist = this._touchDist(e.touches)
    }
  }

  _onTouchMove(e: TouchEvent): void {
    e.preventDefault()
    if (e.touches.length === 1 && this._lastPanPos && this._touchStartPos) {
      const dx = e.touches[0].clientX - this._lastPanPos.x
      const dy = e.touches[0].clientY - this._lastPanPos.y
      const tx = e.touches[0].clientX - this._touchStartPos.x
      const ty = e.touches[0].clientY - this._touchStartPos.y
      if (Math.sqrt(tx * tx + ty * ty) > 8) this._touchMoved = true
      this.panX += dx
      this.panY += dy
      this._lastPanPos = { x: e.touches[0].clientX, y: e.touches[0].clientY }
      this.render()
    } else if (e.touches.length === 2 && this._pinchStartDist) {
      const dist = this._touchDist(e.touches)
      const factor = dist / this._pinchStartDist
      const rect = this.canvas.getBoundingClientRect()
      const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left
      const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top
      this._zoomAround(cx, cy, factor)
      this._pinchStartDist = dist
    }
  }

  _onTouchEnd(e: TouchEvent): void {
    if (e.changedTouches.length === 1 && e.touches.length === 0 && !this._touchMoved) {
      const touch = e.changedTouches[0]
      this._handleClick({
        clientX: touch.clientX,
        clientY: touch.clientY,
      })
    }
    this._lastPanPos = null
    this._touchMoved = false
  }

  _touchDist(touches: TouchList): number {
    const dx = touches[0].clientX - touches[1].clientX
    const dy = touches[0].clientY - touches[1].clientY
    return Math.sqrt(dx * dx + dy * dy)
  }

  _zoomAround(cx: number, cy: number, factor: number): void {
    const newZoom = Math.max(0.25, Math.min(4, this.zoom * factor))
    const scale = newZoom / this.zoom
    this.panX = cx - scale * (cx - this.panX)
    this.panY = cy - scale * (cy - this.panY)
    this.zoom = newZoom
    this.render()
  }

  // -------------------------------------------------------------------------
  // Canvas sizing
  // -------------------------------------------------------------------------

  _initResize(): void {
    const target = this.canvas.parentElement || this.canvas
    this._resizeCanvas()
    const ro = new ResizeObserver(() => {
      this._resizeCanvas()
      if (this.board) this._fitToCanvas()
      this.render()
    })
    ro.observe(target)
  }

  _resizeCanvas(): void {
    const parent = this.canvas.parentElement
    if (!parent) return
    const w = parent.clientWidth || 600
    const h = parent.clientHeight || 600
    this.canvas.style.width = w + 'px'
    this.canvas.style.height = h + 'px'
    this.canvas.width = Math.round(w * this.dpr)
    this.canvas.height = Math.round(h * this.dpr)
  }

  // -------------------------------------------------------------------------
  // Utility
  // -------------------------------------------------------------------------

  /** Lighten a hex colour string (#rrggbb) by `amount` (0–1). */
  _lighten(hex: string, amount: number): string {
    if (!hex.startsWith('#') || hex.length < 7) return hex
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    const l = (c: number) => Math.min(255, c + Math.round((255 - c) * amount))
    return `rgb(${l(r)},${l(g)},${l(b)})`
  }
}
