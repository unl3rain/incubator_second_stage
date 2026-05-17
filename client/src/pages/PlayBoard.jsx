import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchWithTokenRefresh } from '../utils/tokenRefresh'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
const TIME_CONTROL_OPTIONS = [1, 3, 5, 10]

function readGameIdFromUrl() {
  return new URLSearchParams(window.location.search).get('game')
}

function writeGameIdToUrl(gameId) {
  const current = new URL(window.location.href)
  current.searchParams.set('game', gameId)
  window.history.replaceState({}, '', current.toString())
}

function clearGameIdFromUrl() {
  const current = new URL(window.location.href)
  current.searchParams.delete('game')
  window.history.replaceState({}, '', current.toString())
}

function buildWsUrl(gameId, playerId = null) {
  const base = new URL(API_BASE)
  const wsUrl = new URL(`/api/ws/games/${gameId}`, `${base.protocol === 'https:' ? 'wss:' : 'ws:'}//${base.host}`)
  if (playerId) {
    wsUrl.searchParams.set('player_id', playerId)
  }
  return wsUrl.toString()
}

function playerSessionStorageKey(gameId) {
  return `checkers.game_session.${gameId}`
}

function readStoredPlayerSession(gameId) {
  if (!gameId) {
    return null
  }

  try {
    const raw = window.sessionStorage.getItem(playerSessionStorageKey(gameId))
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || !parsed.player_id) {
      return null
    }

    return {
      player_id: parsed.player_id,
      color: parsed.color || null,
      nickname: parsed.nickname || null,
      city: parsed.city || null,
      profile_id: parsed.profile_id || null,
    }
  } catch {
    return null
  }
}

function writeStoredPlayerSession(gameId, session) {
  if (!gameId || !session?.player_id) {
    return
  }

  window.sessionStorage.setItem(playerSessionStorageKey(gameId), JSON.stringify(session))
}

function clearStoredPlayerSession(gameId) {
  if (!gameId) {
    return
  }

  window.sessionStorage.removeItem(playerSessionStorageKey(gameId))
}

function resolvePlayerIdFromGame(gameState, profileId) {
  if (!gameState || !profileId) {
    return null
  }

  const white = gameState.players?.white
  if (white?.profile_id === profileId && white?.player_id) {
    return white.player_id
  }

  const red = gameState.players?.red
  if (red?.profile_id === profileId && red?.player_id) {
    return red.player_id
  }

  return null
}

function formatClock(ms) {
  const safe = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(safe / 60)
  const seconds = safe % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function parseApiDate(value) {
  if (!value || typeof value !== 'string') {
    return null
  }

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  const timestamp = new Date(normalized).getTime()
  return Number.isFinite(timestamp) ? timestamp : null
}

function squareClass(row, col, selected, legalTarget, boardSkin) {
  const dark = (row + col) % 2 === 1
  let base = dark ? 'bg-emerald-900 text-white' : 'bg-amber-100 text-slate-900'
  let accent = legalTarget ? 'ring-4 ring-amber-300 ring-inset' : ''

  if (boardSkin === 'carbon') {
    base = dark ? 'bg-slate-900 text-white' : 'bg-slate-300 text-slate-900'
    accent = legalTarget ? 'ring-4 ring-cyan-300 ring-inset' : ''
  } else if (boardSkin === 'sunset') {
    base = dark ? 'bg-orange-900 text-white' : 'bg-amber-200 text-amber-950'
    accent = legalTarget ? 'ring-4 ring-rose-300 ring-inset' : ''
  } else if (boardSkin === 'ocean') {
    base = dark ? 'bg-teal-950 text-white' : 'bg-cyan-200 text-slate-900'
    accent = legalTarget ? 'ring-4 ring-sky-300 ring-inset' : ''
  } else if (boardSkin === 'ruby') {
    base = dark ? 'bg-rose-950 text-white' : 'bg-pink-200 text-rose-900'
    accent = legalTarget ? 'ring-4 ring-fuchsia-300 ring-inset' : ''
  }

  const active = selected ? 'shadow-[inset_0_0_0_3px_rgba(15,118,110,0.9)]' : ''
  return `${base} ${accent} ${active}`
}

function pieceClass(piece, pieceSkin) {
  if (pieceSkin === 'wood') {
    return piece.player === 'white'
      ? 'bg-gradient-to-br from-amber-100 via-amber-300 to-amber-600 text-amber-950'
      : 'bg-gradient-to-br from-orange-300 via-orange-700 to-orange-950 text-amber-50'
  }

  if (pieceSkin === 'neon') {
    return piece.player === 'white'
      ? 'bg-gradient-to-br from-cyan-200 via-cyan-400 to-blue-500 text-slate-950'
      : 'bg-gradient-to-br from-fuchsia-300 via-fuchsia-600 to-indigo-900 text-white'
  }

  if (pieceSkin === 'gold') {
    return piece.player === 'white'
      ? 'bg-gradient-to-br from-yellow-100 via-yellow-300 to-yellow-500 text-yellow-900'
      : 'bg-gradient-to-br from-amber-300 via-amber-600 to-amber-900 text-amber-50'
  }

  if (pieceSkin === 'crystal') {
    return piece.player === 'white'
      ? 'bg-gradient-to-br from-sky-100 via-cyan-100 to-slate-200 text-slate-900'
      : 'bg-gradient-to-br from-indigo-200 via-violet-400 to-slate-900 text-white'
  }

  if (pieceSkin === 'shadow') {
    return piece.player === 'white'
      ? 'bg-slate-300 text-slate-900'
      : 'bg-slate-900 text-white'
  }

  return piece.player === 'white'
    ? 'bg-gradient-to-br from-slate-50 via-slate-200 to-slate-500 text-slate-900'
    : 'bg-gradient-to-br from-rose-300 via-rose-600 to-rose-950 text-white'
}

export default function PlayBoard({ auth }) {
  const isPro = auth?.subscription === 'pro'
  const [game, setGame] = useState(null)
  const [selected, setSelected] = useState(null)
  const [playerSession, setPlayerSession] = useState(null)
  const [loading, setLoading] = useState(false)
  const [gameError, setGameError] = useState('')
  const [socketStatus, setSocketStatus] = useState('disconnected')
  const [nickname, setNickname] = useState(auth.username || 'Guest')
  const [city, setCity] = useState('Almaty')
  const [preferredColor, setPreferredColor] = useState('white')
  const [gameMode, setGameMode] = useState('pvp')
  const [lobbyMode, setLobbyMode] = useState('ai')
  const [aiElo, setAiElo] = useState(1200)
  const [rankedEnabled, setRankedEnabled] = useState(false)
  const [timeControlMinutes, setTimeControlMinutes] = useState(5)
  const [historyFilter, setHistoryFilter] = useState('all')
  const [boardSkin, setBoardSkin] = useState(() => window.localStorage.getItem('checkers.board_skin') || 'classic')
  const [pieceSkin, setPieceSkin] = useState(() => window.localStorage.getItem('checkers.piece_skin') || 'marble')
  const [showingQuickPlay, setShowingQuickPlay] = useState(false)
  const [quickPlayTicket, setQuickPlayTicket] = useState('')
  const [quickPlayState, setQuickPlayState] = useState('idle')
  const [quickPlayMessage, setQuickPlayMessage] = useState('')
  const [quickPlayQueueSize, setQuickPlayQueueSize] = useState(0)
  const [loadingCreate, setLoadingCreate] = useState(false)
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatMessage, setChatMessage] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [clockNow, setClockNow] = useState(Date.now())
  const [rankedResult, setRankedResult] = useState(null)

  const boardGridRef = useRef(null)
  const wsRef = useRef(null)
  const selectedRef = useRef(null)

  useEffect(() => {
    const syncSkins = () => {
      setBoardSkin(window.localStorage.getItem('checkers.board_skin') || 'classic')
      setPieceSkin(window.localStorage.getItem('checkers.piece_skin') || 'marble')
    }

    const onStorage = (event) => {
      if (!event || event.key === 'checkers.board_skin' || event.key === 'checkers.piece_skin') {
        syncSkins()
      }
    }

    window.addEventListener('storage', onStorage)
    window.addEventListener('checkers-skins-updated', syncSkins)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('checkers-skins-updated', syncSkins)
    }
  }, [])

  useEffect(() => {
    if (isPro) {
      return
    }

    let updated = false
    const boardSkinValue = window.localStorage.getItem('checkers.board_skin')
    const pieceSkinValue = window.localStorage.getItem('checkers.piece_skin')

    if (boardSkinValue && boardSkinValue !== 'classic') {
      window.localStorage.setItem('checkers.board_skin', 'classic')
      setBoardSkin('classic')
      updated = true
    }

    if (pieceSkinValue && pieceSkinValue !== 'marble') {
      window.localStorage.setItem('checkers.piece_skin', 'marble')
      setPieceSkin('marble')
      updated = true
    }

    if (updated) {
      window.dispatchEvent(new Event('checkers-skins-updated'))
    }
  }, [isPro])

  useEffect(() => {
    selectedRef.current = selected
  }, [selected])

  useEffect(() => {
    if (!game?.clock_enabled || game.winner) {
      return undefined
    }

    const interval = window.setInterval(() => setClockNow(Date.now()), 250)
    return () => window.clearInterval(interval)
  }, [game?.game_id, game?.clock_enabled, game?.winner])

  useEffect(() => {
    if (!game?.game_id || !game.clock_enabled || game.winner) {
      return undefined
    }

    let isMounted = true
    const interval = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/games/${encodeURIComponent(game.game_id)}`)
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`)
        }

        if (isMounted) {
          setGame(data)
        }
      } catch {
        // keep the locally ticking clock; server will correct on next successful refresh
      }
    }, 1000)

    return () => {
      isMounted = false
      window.clearInterval(interval)
    }
  }, [game?.game_id, game?.clock_enabled, game?.winner])

  const labels = useMemo(() => ({
    white: game?.players?.white?.nickname || 'White',
    red: game?.players?.red?.nickname || 'Red',
  }), [game])
  const currentPlayerColor = playerSession?.color || null

  const moveTargets = useMemo(() => {
    if (!game || !selected) {
      return []
    }

    return (game.legal_moves || []).filter(
      (move) => move.from[0] === selected[0] && move.from[1] === selected[1],
    )
  }, [game, selected])


  const legalTargetSet = useMemo(() => new Set(moveTargets.map((move) => `${move.to[0]}-${move.to[1]}`)), [moveTargets])

  const joinGame = async (gameId, options = {}) => {
    const payload = {
      city,
      preferred_color: options.preferredColor || preferredColor,
      player_id: options.playerId || playerSession?.player_id || null,
      profile_id: auth.profileId || null,
    }
    console.log('[joinGame] Sending payload:', payload)
    const response = await fetch(`${API_BASE}/games/${encodeURIComponent(gameId)}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = await response.json().catch(() => ({}))
    console.log('[joinGame] Response:', data)
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`)
    }

    setGame(data.game)
    setRankedResult(null)
    if (data.color) {
      const nextSession = {
        player_id: data.player_id,
        color: data.color,
        nickname: data.nickname,
        city: data.city,
        profile_id: data.profile_id,
      }
      setPlayerSession(nextSession)
      writeStoredPlayerSession(data.game.game_id, nextSession)
    } else {
      setPlayerSession(null)
      clearStoredPlayerSession(data.game.game_id)
    }
    setSelected(null)
    setGameError('')
    return data
  }

  const loadGame = async (gameId) => {
    if (!gameId) {
      return
    }

    setLoading(true)
    setGameError('')

    try {
      const response = await fetch(`${API_BASE}/games/${encodeURIComponent(gameId)}`)
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setGame(data)
      setSelected(null)
      setRankedResult(null)
      setGameMode(data.mode || 'pvp')
      setRankedEnabled(Boolean(data.ranked))
      if (typeof data.ai_elo === 'number') setAiElo(data.ai_elo)
      if (typeof data.time_control_minutes === 'number') setTimeControlMinutes(data.time_control_minutes)
      writeGameIdToUrl(data.game_id)

      const storedSession = readStoredPlayerSession(data.game_id)
      const seatPlayerId = resolvePlayerIdFromGame(data, auth.profileId)
      if (storedSession?.player_id || auth.profileId) {
        await joinGame(data.game_id, {
          playerId: storedSession?.player_id || seatPlayerId || null,
          preferredColor: storedSession?.color || preferredColor,
        })
      }
    } catch (error) {
      setGameError(`Could not load game (${error.message})`)
    } finally {
      setLoading(false)
    }
  }

  const createGame = async (overrides = {}) => {
    setLoadingCreate(true)
    setGameError('')

    try {
      const shouldAutoJoin = overrides.autoJoin !== false
      const response = await fetch(`${API_BASE}/games`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: overrides.mode || gameMode,
          ai_elo: typeof overrides.aiElo === 'number' ? overrides.aiElo : aiElo,
          ai_color: overrides.aiColor || 'red',
          ranked: typeof overrides.ranked === 'boolean' ? overrides.ranked : rankedEnabled,
          time_control_minutes: typeof overrides.timeControlMinutes === 'number' ? overrides.timeControlMinutes : timeControlMinutes,
          board: overrides.board || undefined,
          turn: overrides.turn || undefined,
          forced_piece: overrides.forcedPiece || undefined,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setGame(data.game)
      setSelected(null)
      setRankedResult(null)
      setGameMode(data.game.mode || 'pvp')
      setRankedEnabled(Boolean(data.game.ranked))
      if (typeof data.game.ai_elo === 'number') setAiElo(data.game.ai_elo)
      if (typeof data.game.time_control_minutes === 'number') setTimeControlMinutes(data.game.time_control_minutes)
      writeGameIdToUrl(data.game.game_id)
      if (shouldAutoJoin) {
        await joinGame(data.game.game_id, overrides.joinOptions || {})
      } else {
        setPlayerSession(null)
        setGameError('Private room created. Share the invite link before anyone takes a seat.')
      }
    } catch (error) {
      setGameError(`Could not start game (${error.message})`)
    } finally {
      setLoadingCreate(false)
    }
  }

  const startAiGame = async () => {
    await createGame({
      mode: 'vs_ai',
      ranked: false,
      timeControlMinutes,
      aiElo,
      aiColor: preferredColor === 'white' ? 'red' : 'white',
      autoJoin: true,
      joinOptions: { preferredColor },
    })
  }

  const startQuickPlay = async () => {
    setQuickPlayMessage('')
    setGameError('')
    try {
      const response = await fetch(`${API_BASE}/quick-play/enqueue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nickname,
          city,
          preferred_color: preferredColor,
          profile_id: auth.profileId || null,
          ranked: true,
          time_control_minutes: timeControlMinutes,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }
      setShowingQuickPlay(true)
      setQuickPlayTicket(data.ticket_id)
      setQuickPlayState(data.status || 'waiting')
      setQuickPlayMessage(data.status === 'matched' ? 'Matched!' : 'Searching for opponent...')
      setQuickPlayQueueSize(data.queue_size || 0)
      if (data.game) {
        setGame(data.game)
        if (data.color) {
          const nextSession = {
            player_id: data.player_id || null,
            color: data.color || null,
            nickname: data.nickname || nickname,
            city: data.city || city,
            profile_id: data.profile_id || auth.profileId || null,
          }
          setPlayerSession(nextSession)
          writeStoredPlayerSession(data.game.game_id, nextSession)
        } else {
          setPlayerSession(null)
          clearStoredPlayerSession(data.game.game_id)
        }
        writeGameIdToUrl(data.game.game_id)
      }
    } catch (error) {
      setQuickPlayMessage(`Quick play failed (${error.message})`)
    }
  }

  const createPrivateGame = async () => {
    await createGame({
      mode: 'pvp',
      ranked: false,
      timeControlMinutes,
      autoJoin: true,
      joinOptions: { preferredColor },
    })
  }

  const submitMove = async (move) => {
    if (!game?.game_id || !playerSession?.player_id) {
      setGameError('Join the game before making a move.')
      return
    }

    setLoading(true)
    setGameError('')

    try {
      let activePlayerId = playerSession.player_id

      for (let attempt = 0; attempt < 2; attempt += 1) {
        const response = await fetch(`${API_BASE}/games/${encodeURIComponent(game.game_id)}/moves`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            from: move.from,
            to: move.to,
            player_id: activePlayerId,
          }),
        })
        const data = await response.json().catch(() => ({}))
        if (response.ok) {
          setGame(data.game)
          setRankedResult(data.ranked_result || null)
          setSelected(data.game.forced_piece || null)
          return
        }

        const detail = data.detail || `HTTP ${response.status}`
        const shouldRecoverPlayer = attempt === 0 && typeof detail === 'string' && /Unknown player/i.test(detail)
        if (!shouldRecoverPlayer) {
          throw new Error(detail)
        }

        const storedSession = readStoredPlayerSession(game.game_id)
        const rejoin = await joinGame(game.game_id, {
          playerId: activePlayerId || storedSession?.player_id || null,
          preferredColor: playerSession?.color || storedSession?.color || preferredColor,
        })
        activePlayerId = rejoin.player_id
      }
    } catch (error) {
      setGameError(`Move rejected: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSquareClick = (row, col) => {
    if (!game || game.winner) {
      return
    }

    if (game.mode === 'pvp' && currentPlayerColor && game.turn !== currentPlayerColor) {
      setGameError(`Wait for ${labels[game.turn]} to move.`)
      return
    }

    const piece = game.board[row]?.[col]
    const legalMove = moveTargets.find((move) => move.to[0] === row && move.to[1] === col)

    if (legalMove && selected && !loading) {
      submitMove(legalMove)
      return
    }

    if (piece && piece.player === game.turn && (game.mode !== 'pvp' || piece.player === currentPlayerColor)) {
      setSelected([row, col])
      return
    }

    if (!game.forced_piece) {
      setSelected(null)
    }
  }

  const handleBoardSquareKeyDown = (event, row, col) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      handleSquareClick(row, col)
      return
    }

    const deltas = {
      ArrowUp: [-1, 0],
      ArrowDown: [1, 0],
      ArrowLeft: [0, -1],
      ArrowRight: [0, 1],
    }
    const delta = deltas[event.key]
    if (!delta) {
      return
    }

    event.preventDefault()
    const nextRow = Math.max(0, Math.min(7, row + delta[0]))
    const nextCol = Math.max(0, Math.min(7, col + delta[1]))
    boardGridRef.current?.querySelector(`[data-square='${nextRow}-${nextCol}']`)?.focus()
  }

  useEffect(() => {
    const gameId = readGameIdFromUrl()
    if (gameId) {
      loadGame(gameId)
      return
    }

    setGame(null)
  }, [])


  // WebSocket connection: reconnect on game, player, or token change
  useEffect(() => {
    if (!game?.game_id || !auth.token) {
      return undefined
    }

    // Always close previous socket
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null
      wsRef.current.close()
      wsRef.current = null
    }

    let isActive = true
    const socket = new WebSocket(buildWsUrl(game.game_id, playerSession?.player_id || null))
    wsRef.current = socket

    socket.onopen = () => { if (isActive) setSocketStatus('connected') }
    socket.onclose = () => { if (isActive) setSocketStatus('disconnected') }
    socket.onerror = () => { if (isActive) setSocketStatus('error') }

    socket.onmessage = (event) => {
      if (!isActive) return
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'game_updated' || message.type === 'game_snapshot') {
          setGame(message.game)
          if (message.game?.forced_piece) {
            setSelected(message.game.forced_piece)
          } else {
            setSelected(null)
          }
          return
        }

        if (message.type === 'chat_message' && message.message) {
          setChatMessages((current) => (current.some((item) => item.message_id === message.message.message_id) ? current : [...current, message.message]))
          return
        }
      } catch {
        setGameError('Received invalid realtime update.')
      }
    }

    return () => {
      isActive = false
      if (wsRef.current === socket) {
        socket.onopen = null
        socket.onclose = null
        socket.onerror = null
        socket.onmessage = null
        socket.close()
        wsRef.current = null
      } else {
        socket.close()
      }
    }
  }, [game?.game_id, playerSession?.player_id, auth.token])

  useEffect(() => {
    if (!game?.game_id || !auth.token) {
      setChatMessages([])
      return undefined
    }

    let isMounted = true
    setChatLoading(true)

    fetchWithTokenRefresh(
      `${API_BASE}/social/chat/${encodeURIComponent(game.game_id)}?limit=50`,
      {
        headers: {},
      },
      auth.token,
      auth.refreshToken,
      handleTokenRefreshed
    )
      .then(async (response) => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`)
        }
        if (isMounted) {
          setChatMessages(data.messages || [])
        }
      })
      .catch((error) => {
        if (isMounted) {
          setChatMessage(`Could not load chat (${error.message})`)
        }
      })
      .finally(() => {
        if (isMounted) {
          setChatLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [game?.game_id, auth.token, auth.refreshToken])

  const handleTokenRefreshed = (newToken, newRefreshToken) => {
    // Update localStorage
    window.localStorage.setItem('checkers.token', newToken)
    if (newRefreshToken) {
      window.localStorage.setItem('checkers.refresh_token', newRefreshToken)
    }
    // Note: Parent App.jsx will detect this change and update state
  }

  const sendChatMessage = async (text, messageType = 'text') => {
    if (!game?.game_id || !auth.token) {
      return
    }

    const payloadText = text.trim()
    if (!payloadText) {
      return
    }

    setChatMessage('')
    try {
      const response = await fetchWithTokenRefresh(
        `${API_BASE}/social/chat/${encodeURIComponent(game.game_id)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text: payloadText, message_type: messageType }),
        },
        auth.token,
        auth.refreshToken,
        handleTokenRefreshed
      )
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setChatInput('')
      // Do not append message here; WebSocket will deliver it
    } catch (error) {
      setChatMessage(`Could not send message (${error.message})`)
    }
  }

  const reportChatMessage = async (messageId) => {
    if (!auth.token) {
      setChatMessage('Sign in to report chat messages.')
      return
    }

    try {
      const response = await fetchWithTokenRefresh(
        `${API_BASE}/social/chat/${encodeURIComponent(messageId)}/report`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason: 'abusive' }),
        },
        auth.token,
        auth.refreshToken,
        handleTokenRefreshed
      )
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setChatMessage('Message reported.')
    } catch (error) {
      setChatMessage(`Could not report message (${error.message})`)
    }
  }

  const cancelQuickPlay = async () => {
    if (!quickPlayTicket) {
      return
    }

    try {
      const response = await fetch(`${API_BASE}/quick-play/status/${encodeURIComponent(quickPlayTicket)}`, {
        method: 'DELETE',
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setShowingQuickPlay(false)
      setQuickPlayState('idle')
      setQuickPlayMessage('Quick play canceled.')
      setQuickPlayTicket('')
      setQuickPlayQueueSize(0)
    } catch (error) {
      setQuickPlayMessage(`Could not cancel quick play (${error.message})`)
    }
  }

  useEffect(() => {
    if (!showingQuickPlay || !quickPlayTicket || quickPlayState === 'matched') {
      return undefined
    }

    let isMounted = true
    const interval = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/quick-play/status/${encodeURIComponent(quickPlayTicket)}`)
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`)
        }

        if (!isMounted) {
          return
        }

        setQuickPlayState(data.status || 'waiting')
        setQuickPlayQueueSize(data.queue_size || 0)

        if (data.status === 'matched') {
          setQuickPlayMessage('Opponent found. Opening board...')
          if (data.game) {
            setGame(data.game)
            if (data.color) {
              const nextSession = {
                player_id: data.player_id || null,
                color: data.color || null,
                nickname: data.nickname || nickname,
                city: data.city || city,
                profile_id: data.profile_id || auth.profileId || null,
              }
              setPlayerSession(nextSession)
              writeStoredPlayerSession(data.game.game_id, nextSession)
            } else {
              setPlayerSession(null)
              clearStoredPlayerSession(data.game.game_id)
            }
            writeGameIdToUrl(data.game.game_id)
          }
        }
      } catch {
        if (isMounted) {
          setQuickPlayMessage('Could not refresh quick play status.')
        }
      }
    }, 3000)

    return () => {
      isMounted = false
      window.clearInterval(interval)
    }
  }, [showingQuickPlay, quickPlayTicket, quickPlayState, nickname, city, auth.profileId])

  const copyInviteLink = async () => {
    if (!game?.game_id) {
      return
    }

    try {
      await navigator.clipboard.writeText(`${window.location.origin}${window.location.pathname}?game=${game.game_id}`)
      setGameError('Invite link copied.')
    } catch {
      setGameError('Could not copy invite link automatically.')
    }
  }

  const returnToLobby = () => {
    const currentGameId = game?.game_id
    setSelected(null)
    setGame(null)
    setPlayerSession(null)
    setChatMessages([])
    setRankedResult(null)
    setShowingQuickPlay(false)
    setQuickPlayState('idle')
    setQuickPlayTicket('')
    setQuickPlayQueueSize(0)
    setQuickPlayMessage('')
    clearStoredPlayerSession(currentGameId)
    clearGameIdFromUrl()
  }

  const board = game?.board || []
  const liveClock = game?.clock_enabled ? (() => {
    const deadline = parseApiDate(game.active_deadline_at)
    const currentTime = clockNow
    const whiteMs = game.white_time_ms ?? 0
    const redMs = game.red_time_ms ?? 0

    if (!deadline || game.winner) {
      return { whiteMs, redMs }
    }

    if (game.turn === 'white') {
      return { whiteMs: Math.max(0, deadline - currentTime), redMs }
    }

    return { whiteMs, redMs: Math.max(0, deadline - currentTime) }
  })() : null
  const didLose = Boolean(game?.winner && currentPlayerColor && game.winner !== currentPlayerColor)
  const didWin = Boolean(game?.winner && currentPlayerColor && game.winner === currentPlayerColor)
  const isBoardFlipped = currentPlayerColor === 'red'
  const isPrivateInviteRoom = game?.mode === 'pvp' && !game?.ranked
  const seatWhiteOpen = !game?.players?.white
  const seatRedOpen = !game?.players?.red
  const historyEntries = (game?.move_history || []).filter((entry) => {
    if (historyFilter === 'ai') return entry.by_ai
    if (historyFilter === 'captures') return Boolean(entry.capture)
    return true
  })

  return (
    <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
      <section className="space-y-6">
        <div className="rounded-[2rem] bg-gradient-to-br from-slate-950 via-teal-900 to-emerald-700 p-6 text-white shadow-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-200">Live board</p>
          <h1 className="mt-2 text-3xl font-bold sm:text-4xl">Play with AI, queue ranked, or send a private room</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <p className="max-w-2xl text-sm text-emerald-50/90">The lobby now has three clear entry modes: practice against AI, find a timed ranked match, or create a private invite link that waits for another player before the game starts.</p>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${isPro ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}>
              {isPro ? 'Pro subscriber' : 'Free user — premium skins blocked'}
            </span>
          </div>
          <div className="mt-5 flex flex-wrap gap-3 text-sm">
            {game?.game_id ? (
              <>
                {isPrivateInviteRoom ? <button type="button" onClick={copyInviteLink} className="rounded-full border border-white/30 px-4 py-2 font-semibold text-white transition hover:bg-white/10">Copy invite</button> : null}
                <button type="button" onClick={returnToLobby} className="rounded-full border border-white/30 px-4 py-2 font-semibold text-white transition hover:bg-white/10">Leave board</button>
              </>
            ) : (
              <p className="rounded-full border border-white/20 px-4 py-2 text-emerald-50/90">Choose one of the three modes below to enter the board.</p>
            )}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <label className="rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Nickname</span>
            <input value={nickname} onChange={(event) => setNickname(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2" />
          </label>
          <label className="rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">City</span>
            <input value={city} onChange={(event) => setCity(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2" />
          </label>
          <label className="rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Color</span>
            <select value={preferredColor} onChange={(event) => setPreferredColor(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2">
              <option value="white">White</option>
              <option value="red">Red</option>
            </select>
          </label>
        </div>

        {gameError ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{gameError}</p> : null}

        {!game ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap gap-2">
              {[
                { key: 'ai', label: 'Play vs AI' },
                { key: 'ranked', label: 'Find ranked match' },
                { key: 'private', label: 'Private invite room' },
              ].map((mode) => (
                <button
                  key={mode.key}
                  type="button"
                  onClick={() => setLobbyMode(mode.key)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${lobbyMode === mode.key ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}
                >
                  {mode.label}
                </button>
              ))}
            </div>

            {lobbyMode === 'ai' ? (
              <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Mode 1</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-900">Practice against the AI</h2>
                  <p className="mt-3 text-sm text-slate-600">Choose the engine strength and clock, then jump straight into a live game. This creates the board and seats you immediately.</p>
                  <button type="button" onClick={startAiGame} disabled={loadingCreate} className="mt-5 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">
                    {loadingCreate ? 'Creating AI game...' : 'Start AI game'}
                  </button>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <label className="block text-xs uppercase tracking-[0.2em] text-slate-500">Time control</label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {TIME_CONTROL_OPTIONS.map((value) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTimeControlMinutes(value)}
                        className={`rounded-full px-3 py-2 text-sm font-semibold transition ${timeControlMinutes === value ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}`}
                      >
                        {value} min
                      </button>
                    ))}
                  </div>
                  <label className="block text-xs uppercase tracking-[0.2em] text-slate-500">AI difficulty</label>
                  <input type="range" min="600" max="2200" step="25" value={aiElo} onChange={(event) => setAiElo(Number(event.target.value))} className="mt-4 w-full" />
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-500"><span>600</span><span className="font-semibold text-slate-900">{aiElo}</span><span>2200</span></div>
                  <p className="mt-4 text-sm text-slate-600">Selected clock: {timeControlMinutes} min. Color preference still applies when you take your seat.</p>
                </div>
              </div>
            ) : null}

            {lobbyMode === 'ranked' ? (
              <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Mode 2</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-900">Find a timed ranked match</h2>
                  <p className="mt-3 text-sm text-slate-600">Pick the clock first, then enter matchmaking. The queue keeps polling until the backend returns an opponent and a live game.</p>
                  <button
                    type="button"
                    onClick={startQuickPlay}
                    disabled={showingQuickPlay && quickPlayState !== 'matched'}
                    className="mt-5 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {showingQuickPlay && quickPlayState !== 'matched' ? 'Searching...' : 'Find match'}
                  </button>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <label className="block text-xs uppercase tracking-[0.2em] text-slate-500">Time control</label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {TIME_CONTROL_OPTIONS.map((value) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTimeControlMinutes(value)}
                        className={`rounded-full px-3 py-2 text-sm font-semibold transition ${timeControlMinutes === value ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}`}
                      >
                        {value} min
                      </button>
                    ))}
                  </div>
                  <p className="mt-4 text-sm text-slate-600">Current preference: {preferredColor} pieces.</p>
                </div>
              </div>
            ) : null}

            {lobbyMode === 'private' ? (
              <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Mode 3</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-900">Create a private invite room</h2>
                  <p className="mt-3 text-sm text-slate-600">This creates a personal game link without seating you automatically. Share the invite first, then either player can open the room and take a color.</p>
                  <button type="button" onClick={createPrivateGame} disabled={loadingCreate} className="mt-5 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">
                    {loadingCreate ? 'Creating room...' : 'Create private room'}
                  </button>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <label className="block text-xs uppercase tracking-[0.2em] text-slate-500">Room timer</label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {TIME_CONTROL_OPTIONS.map((value) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTimeControlMinutes(value)}
                        className={`rounded-full px-3 py-2 text-sm font-semibold transition ${timeControlMinutes === value ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}`}
                      >
                        {value} min
                      </button>
                    ))}
                  </div>
                  <p className="mt-4 text-sm text-slate-600">After creation, use the invite button on the room header to share the link.</p>
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {game ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Match</p>
                <h2 className="mt-1 text-2xl font-semibold text-slate-900">{game.game_id}</h2>
                <p className="mt-1 text-sm text-slate-500">Mode: {game.mode} • Turn: {game.turn} • Socket: {socketStatus}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <p className="font-semibold text-slate-900">{game.winner ? `Winner: ${labels[game.winner]}` : `To move: ${labels[game.turn]}`}</p>
                {liveClock ? <p className="mt-1">W {formatClock(liveClock.whiteMs)} • R {formatClock(liveClock.redMs)}</p> : null}
              </div>
            </div>

            {game.winner ? (
              <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 px-4">
                <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Game over</p>
                  <h3 className="mt-2 text-2xl font-bold text-slate-900">
                    {didWin ? 'You won the match' : didLose ? 'You lost the match' : 'Match finished'}
                  </h3>
                  <p className="mt-3 text-sm text-slate-600">
                    Winner: {labels[game.winner] || game.winner}{game.winner_reason ? ` • Reason: ${game.winner_reason}` : ''}
                  </p>
                  {rankedResult ? (
                    <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                      <p className="font-semibold text-slate-900">Ranked result</p>
                      <p className="mt-1">ELO {rankedResult.before} → {rankedResult.after} ({rankedResult.delta >= 0 ? '+' : ''}{rankedResult.delta})</p>
                      <p className="mt-1 text-xs text-slate-500">Season {rankedResult.season_key}</p>
                    </div>
                  ) : null}
                  <div className="mt-5 flex flex-wrap gap-3">
                    <button type="button" onClick={returnToLobby} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700">Back to lobby</button>
                    <button type="button" onClick={() => game.game_id && loadGame(game.game_id)} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Refresh state</button>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
              <div className="overflow-hidden rounded-[1.5rem] border border-slate-200 bg-slate-50 p-3">
                <div ref={boardGridRef} className={`grid grid-cols-8 gap-0 ${isBoardFlipped ? 'rotate-180' : ''} ${boardSkin === 'carbon' ? 'bg-slate-900' : boardSkin === 'sunset' ? 'bg-orange-900' : boardSkin === 'ocean' ? 'bg-teal-950' : boardSkin === 'ruby' ? 'bg-rose-950' : 'bg-emerald-900'}`}>
                  {board.map((row, rowIndex) => row.map((piece, colIndex) => {
                    const selectedHere = Boolean(selected && selected[0] === rowIndex && selected[1] === colIndex)
                    const legalTarget = legalTargetSet.has(`${rowIndex}-${colIndex}`)
                    const ariaLabel = piece
                      ? `${piece.player} ${piece.king ? 'king' : 'man'} at row ${8 - rowIndex}, column ${colIndex + 1}`
                      : `Empty square at row ${8 - rowIndex}, column ${colIndex + 1}`

                    return (
                      <button
                        key={`${rowIndex}-${colIndex}`}
                        data-square={`${rowIndex}-${colIndex}`}
                        type="button"
                        onClick={() => handleSquareClick(rowIndex, colIndex)}
                        onKeyDown={(event) => handleBoardSquareKeyDown(event, rowIndex, colIndex)}
                        className={`relative aspect-square flex items-center justify-center transition ${isBoardFlipped ? 'rotate-180' : ''} ${squareClass(rowIndex, colIndex, selectedHere, legalTarget, boardSkin)}`}
                        aria-label={ariaLabel}
                      >
                        {piece ? (
                          <span className={`flex h-10 w-10 items-center justify-center rounded-full border-2 border-white/50 shadow-lg ${pieceClass(piece, pieceSkin)}`}>
                            <span className="text-[10px] font-bold uppercase tracking-wider">{piece.king ? 'K' : ''}</span>
                          </span>
                        ) : null}
                        {selectedHere ? <span className="absolute inset-2 rounded-full ring-4 ring-amber-300" /> : null}
                      </button>
                    )
                  }))}
                </div>
              </div>

              <aside className="space-y-4">
                <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Player seat</p>
                  <p className="mt-2 text-sm text-slate-600">{playerSession?.color ? `Joined as ${playerSession.nickname} (${playerSession.color})` : game.mode === 'pvp' ? 'You are spectating this room.' : 'Not seated yet'}</p>
                  {game.mode === 'pvp' ? (
                    <div className="mt-3 space-y-2 text-xs">
                      <p className="text-slate-500">PvP rooms use your color preference for seating. White: {seatWhiteOpen ? 'open' : 'taken'} • Red: {seatRedOpen ? 'open' : 'taken'}</p>
                      {!playerSession?.color && (seatWhiteOpen || seatRedOpen) ? (
                        <div className="mt-4 p-4 rounded-xl border-2 border-emerald-400 bg-emerald-50 flex flex-col items-center">
                          <p className="mb-2 text-base font-semibold text-emerald-900">You can join this game!</p>
                          <p className="mb-3 text-sm text-emerald-800">Click below to take a seat with your preferred color.</p>
                          <button
                            type="button"
                            onClick={async () => {
                              console.log('[Join Button] Clicked')
                              setGameError('')
                              try {
                                await joinGame(game.game_id)
                                // Reload game state to reflect new seat assignment
                                await loadGame(game.game_id)
                              } catch (err) {
                                setGameError(err?.message || 'Failed to join room. No seats available.')
                              }
                            }}
                            className="w-full rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white text-base shadow-lg transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                          >
                            Join room with preferred color
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Match setup</p>
                  <div className="mt-3 space-y-2 text-sm text-slate-600">
                    <p><span className="font-semibold text-slate-900">Mode:</span> {game.mode === 'vs_ai' ? 'AI game' : game.ranked ? 'Ranked PvP' : 'Private PvP'}</p>
                    <p><span className="font-semibold text-slate-900">Clock:</span> {game.time_control_minutes ? `${game.time_control_minutes} min` : 'Untimed'}</p>
                    {game.mode === 'vs_ai' ? <p><span className="font-semibold text-slate-900">AI difficulty:</span> {game.ai_elo}</p> : null}
                    <p><span className="font-semibold text-slate-900">Preferred color:</span> {preferredColor}</p>
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Move history</p>
                  <div className="mt-3 flex gap-2 text-xs">
                    {['all', 'captures', 'ai'].map((value) => (
                      <button key={value} type="button" onClick={() => setHistoryFilter(value)} className={`rounded-full px-3 py-2 font-semibold ${historyFilter === value ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700'}`}>
                        {value}
                      </button>
                    ))}
                  </div>
                  <div className="mt-3 max-h-56 space-y-2 overflow-auto text-xs text-slate-600">
                    {historyEntries.length ? historyEntries.map((entry, index) => (
                      <div key={`${index}-${entry.from.join('-')}-${entry.to.join('-')}`} className="rounded-lg bg-slate-50 p-3">
                        {entry.player}: {entry.from.join(', ')} → {entry.to.join(', ')}{entry.capture ? ` capture ${entry.capture.join(', ')}` : ''}
                      </div>
                    )) : <p>No moves yet.</p>}
                  </div>
                </section>
              </aside>
            </div>
          </div>
        ) : null}
      </section>

      <aside className="space-y-4">
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Social chat</p>
          <div className="mt-3 max-h-80 space-y-2 overflow-auto text-sm">
            {chatLoading ? <p className="text-slate-500">Loading chat...</p> : null}
            {chatMessages.length ? chatMessages.map((item) => (
              <div key={item.message_id} className="rounded-2xl bg-slate-50 p-3">
                <p className="text-xs font-semibold text-slate-500">{item.sender_nickname}</p>
                <p className="mt-1 text-slate-800">{item.text}</p>
                <button type="button" onClick={() => reportChatMessage(item.message_id)} className="mt-2 rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-100">
                  Report
                </button>
              </div>
            )) : <p className="text-slate-500">No chat messages yet.</p>}
          </div>
          {chatMessage ? <p className="mt-3 text-xs text-rose-700">{chatMessage}</p> : null}
          <div className="mt-3 flex gap-2">
            <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Say something..." className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm" />
            <button type="button" onClick={() => sendChatMessage(chatInput)} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700">Send</button>
          </div>
        </section>

        {showingQuickPlay ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Matchmaking status</p>
            <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
              <p className="font-semibold text-slate-900">{quickPlayState}</p>
              <p className="mt-1">Ticket: {quickPlayTicket || 'none'}</p>
              <p>Queue: {quickPlayQueueSize}</p>
              <p className="mt-1">{quickPlayMessage}</p>
              {quickPlayState !== 'matched' ? (
                <button type="button" onClick={cancelQuickPlay} className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100">
                  Cancel queue
                </button>
              ) : null}
            </div>
          </section>
        ) : null}
      </aside>
    </div>
  )
}
