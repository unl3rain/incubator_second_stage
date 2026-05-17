import { useEffect, useMemo, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

function boardSquareClass(row, col, boardSkin) {
  const dark = (row + col) % 2 === 1
  if (boardSkin === 'carbon') {
    return dark ? 'bg-slate-900 text-white' : 'bg-slate-300 text-slate-900'
  }
  if (boardSkin === 'sunset') {
    return dark ? 'bg-orange-900 text-white' : 'bg-amber-200 text-amber-950'
  }
  return dark ? 'bg-emerald-900 text-white' : 'bg-amber-100 text-slate-900'
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

  return piece.player === 'white'
    ? 'bg-slate-200 text-slate-900'
    : 'bg-rose-700 text-white'
}

const trainingTracks = [
  { name: 'Position editor', status: 'live', detail: 'Custom setup launch into training is already present on the backend.' },
  { name: 'AI coach', status: 'live', detail: 'Coach feedback and advanced engine status are available now.' },
  { name: 'Opening explorer', status: 'next', detail: 'Opening explorer MVP is one of the current product priorities.' },
  { name: 'Endgame trainer', status: 'planned', detail: 'Still incomplete in the brief, but this page now reserves a dedicated surface for it.' },
]

function getMatchLabel(match) {
  const whiteName = match?.players?.white?.nickname || 'White'
  const redName = match?.players?.red?.nickname || 'Red'
  return `${whiteName} vs ${redName}`
}

export default function Training({ auth }) {
  const isPro = auth?.subscription === 'pro'
  const [engine, setEngine] = useState(null)
  const [recentMatches, setRecentMatches] = useState([])
  const [trainingGame, setTrainingGame] = useState(null)
  const [trainingSeatIds, setTrainingSeatIds] = useState({ white: '', red: '' })
  const [trainingMode, setTrainingMode] = useState('self')
  const [aiElo, setAiElo] = useState(1200)
  const [selectedSquare, setSelectedSquare] = useState(null)
  const [coachFeedback, setCoachFeedback] = useState(null)
  const [coachHistory, setCoachHistory] = useState([])
  const [showOldEvaluations, setShowOldEvaluations] = useState(false)
  const [trainingBusy, setTrainingBusy] = useState(false)
  const [trainingMessage, setTrainingMessage] = useState('')
  const [error, setError] = useState('')
  const [boardSkin, setBoardSkin] = useState(() => window.localStorage.getItem('checkers.board_skin') || 'classic')
  const [pieceSkin, setPieceSkin] = useState(() => window.localStorage.getItem('checkers.piece_skin') || 'marble')

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

  const moveTargets = useMemo(() => {
    if (!trainingGame || !selectedSquare) {
      return []
    }

    return (trainingGame.legal_moves || []).filter((move) => move.from[0] === selectedSquare[0] && move.from[1] === selectedSquare[1])
  }, [trainingGame, selectedSquare])

  const legalTargetSet = useMemo(
    () => new Set(moveTargets.map((move) => `${move.to[0]}-${move.to[1]}`)),
    [moveTargets],
  )

  // Load custom training game if one was created from position editor
  useEffect(() => {
    let isMounted = true

    async function loadCustomGame() {
      const customGameId = window.localStorage.getItem('custom_training_game_id')
      if (!customGameId) return

      try {
        const response = await fetch(`${API_BASE}/games/${encodeURIComponent(customGameId)}`)
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`)
        }

        if (!isMounted) return

        const game = data
        const isSelfMode = game.mode === 'training'
        
        const whiteJoinResponse = await fetch(`${API_BASE}/games/${encodeURIComponent(game.game_id)}/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            nickname: 'Trainer White',
            city: 'Almaty',
            preferred_color: 'white',
          }),
        })
        const whiteJoinData = await whiteJoinResponse.json().catch(() => ({}))
        if (!whiteJoinResponse.ok) {
          throw new Error(whiteJoinData.detail || `HTTP ${whiteJoinResponse.status}`)
        }

        let redPlayerId = ''
        if (isSelfMode) {
          const redJoinResponse = await fetch(`${API_BASE}/games/${encodeURIComponent(game.game_id)}/join`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              nickname: 'Trainer Red',
              city: 'Almaty',
              preferred_color: 'red',
            }),
          })
          const redJoinData = await redJoinResponse.json().catch(() => ({}))
          if (!redJoinResponse.ok) {
            throw new Error(redJoinData.detail || `HTTP ${redJoinResponse.status}`)
          }
          redPlayerId = redJoinData.player_id
        }

        if (isMounted) {
          setTrainingGame(whiteJoinData.game)
          setTrainingSeatIds({ white: whiteJoinData.player_id, red: redPlayerId })
          const modeMessage = isSelfMode 
            ? 'Custom position loaded for self-analysis. You can move both colors.'
            : 'Custom position loaded. Play white against the AI.'
          setTrainingMessage(modeMessage)
          window.localStorage.removeItem('custom_training_game_id')
        }
      } catch (err) {
        if (isMounted) {
          setError(`Could not load custom position (${err.message})`)
          window.localStorage.removeItem('custom_training_game_id')
        }
      }
    }

    loadCustomGame()
    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    async function load() {
      try {
        const [engineResponse, matchesResponse] = await Promise.all([
          fetch(`${API_BASE}/engine/status`),
          fetch(`${API_BASE}/matches/recent?limit=4`),
        ])
        const [engineData, matchesData] = await Promise.all([
          engineResponse.json(),
          matchesResponse.json(),
        ])

        if (!isMounted) {
          return
        }

        setEngine(engineData)
        setRecentMatches(matchesData.matches || [])
      } catch {
        if (isMounted) {
          setError('Training signals are unavailable.')
        }
      }
    }

    load()
    return () => {
      isMounted = false
    }
  }, [])

  const startTrainingSession = async () => {
    setTrainingBusy(true)
    setTrainingMessage('')
    setCoachFeedback(null)
    setCoachHistory([])
    setShowOldEvaluations(false)

    try {
      const isSelfMode = trainingMode === 'self'
      const createResponse = await fetch(`${API_BASE}/games`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          isSelfMode
            ? { mode: 'training' }
            : { mode: 'vs_ai', ai_elo: aiElo, ai_color: 'red', ranked: false },
        ),
      })
      const createData = await createResponse.json().catch(() => ({}))
      if (!createResponse.ok) {
        throw new Error(createData.detail || `HTTP ${createResponse.status}`)
      }

      const game = createData.game
      const whiteJoinResponse = await fetch(`${API_BASE}/games/${encodeURIComponent(game.game_id)}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nickname: 'Trainer White',
          city: 'Almaty',
          preferred_color: 'white',
        }),
      })
      const whiteJoinData = await whiteJoinResponse.json().catch(() => ({}))
      if (!whiteJoinResponse.ok) {
        throw new Error(whiteJoinData.detail || `HTTP ${whiteJoinResponse.status}`)
      }

      let redPlayerId = ''
      if (isSelfMode) {
        const redJoinResponse = await fetch(`${API_BASE}/games/${encodeURIComponent(game.game_id)}/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            nickname: 'Trainer Red',
            city: 'Almaty',
            preferred_color: 'red',
          }),
        })
        const redJoinData = await redJoinResponse.json().catch(() => ({}))
        if (!redJoinResponse.ok) {
          throw new Error(redJoinData.detail || `HTTP ${redJoinResponse.status}`)
        }
        redPlayerId = redJoinData.player_id
      }

      setTrainingGame(whiteJoinData.game)
      setTrainingSeatIds({ white: whiteJoinData.player_id, red: redPlayerId })
      setSelectedSquare(null)
      setTrainingMessage(
        isSelfMode
          ? 'Self-analysis mode started. You can move both colors and coach evaluates both sides.'
          : `AI sparring started (ELO ${aiElo}). Coach evaluates your move and AI reply.`,
      )
    } catch (sessionError) {
      setTrainingMessage(`Could not start training session (${sessionError.message})`)
    } finally {
      setTrainingBusy(false)
    }
  }

  const submitTrainingMove = async (move) => {
    if (!trainingGame?.game_id) {
      return
    }

    const activePlayerId = trainingMode === 'self'
      ? trainingSeatIds[trainingGame.turn]
      : trainingSeatIds.white

    if (!activePlayerId) {
      setTrainingMessage('No active seat for this side. Restart training session.')
      return
    }

    setTrainingBusy(true)
    setTrainingMessage('')
    try {
      const response = await fetch(`${API_BASE}/games/${encodeURIComponent(trainingGame.game_id)}/moves`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from: move.from,
          to: move.to,
          player_id: activePlayerId,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setTrainingGame(data.game)
      const nextFeedbackHistory = (data.coach_feedback_history && data.coach_feedback_history.length)
        ? data.coach_feedback_history
        : (data.coach_feedback ? [data.coach_feedback] : [])
      const stamped = nextFeedbackHistory.map((entry, index) => ({
        ...entry,
        entry_id: `${Date.now()}-${index}-${Math.random().toString(16).slice(2)}`,
      }))
      if (stamped.length) {
        setCoachHistory((current) => [...current, ...stamped])
        setCoachFeedback(stamped[stamped.length - 1])
      } else {
        setCoachFeedback(null)
      }
      setSelectedSquare(data.game?.forced_piece || null)
    } catch (moveError) {
      setTrainingMessage(`Move failed (${moveError.message})`)
    } finally {
      setTrainingBusy(false)
    }
  }

  const handleSquareClick = (row, col) => {
    if (!trainingGame || trainingGame.winner || trainingBusy) {
      return
    }

    const legalMove = moveTargets.find((move) => move.to[0] === row && move.to[1] === col)
    if (legalMove) {
      submitTrainingMove(legalMove)
      return
    }

    const piece = trainingGame.board?.[row]?.[col]
    if (piece && piece.player === trainingGame.turn) {
      setSelectedSquare([row, col])
      return
    }

    setSelectedSquare(null)
  }

  const undoMove = async () => {
    const undoPlayerId = trainingSeatIds.white || trainingSeatIds.red
    if (!trainingGame?.game_id || !undoPlayerId) {
      return
    }

    setTrainingBusy(true)
    setTrainingMessage('')
    try {
      const response = await fetch(`${API_BASE}/games/${encodeURIComponent(trainingGame.game_id)}/undo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: undoPlayerId }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setTrainingGame(data.game)
      setSelectedSquare(null)
      setCoachFeedback(null)
    } catch (undoError) {
      setTrainingMessage(`Could not undo (${undoError.message})`)
    } finally {
      setTrainingBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-gradient-to-br from-emerald-100 via-white to-cyan-50 p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Training</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">Dedicated practice modes, not a dashboard dump</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          This page is now scoped to training surfaces: engine-backed coaching, the position editor track, and the next training modules from the product brief.
        </p>
      </section>

      {error ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p> : null}
      {trainingMessage ? <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">{trainingMessage}</p> : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        {!isPro ? (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            Training launch and coaching are Pro-only features.
            <button
              type="button"
              onClick={auth?.openDemoPayment}
              className="ml-3 rounded-lg bg-amber-100 px-3 py-1 font-semibold text-amber-900 transition hover:bg-amber-200"
            >
              Upgrade to Pro
            </button>
          </div>
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Interactive coach</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900">Training board</h2>
            <p className="mt-1 text-sm text-slate-600">Pick self-analysis (both sides by you) or AI sparring with configurable difficulty.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select value={trainingMode} onChange={(event) => setTrainingMode(event.target.value)} className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
              <option value="self">Self-analysis (both sides)</option>
              <option value="vs_ai">AI sparring</option>
            </select>
            {trainingMode === 'vs_ai' ? (
              <label className="flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
                AI ELO
                <input
                  type="number"
                  min={600}
                  max={2200}
                  step={25}
                  value={aiElo}
                  onChange={(event) => setAiElo(Number(event.target.value) || 1200)}
                  className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
            ) : null}
            <button type="button" onClick={startTrainingSession} disabled={trainingBusy || !isPro} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">
              {trainingBusy ? 'Working...' : 'Start training'}
            </button>
            <button type="button" onClick={undoMove} disabled={trainingBusy || !trainingGame} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">
              Undo
            </button>
          </div>
        </div>

        {trainingGame ? (
          <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_0.9fr]">
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-3">
              <div className="grid grid-cols-8 gap-0">
                {trainingGame.board.map((row, rowIndex) => row.map((piece, colIndex) => {
                  const isSelected = selectedSquare && selectedSquare[0] === rowIndex && selectedSquare[1] === colIndex
                  const isTarget = legalTargetSet.has(`${rowIndex}-${colIndex}`)
                  return (
                    <button
                      key={`training-${rowIndex}-${colIndex}`}
                      type="button"
                      onClick={() => handleSquareClick(rowIndex, colIndex)}
                      className={`relative aspect-square flex items-center justify-center ${boardSquareClass(rowIndex, colIndex, boardSkin)} ${isSelected ? 'ring-4 ring-amber-300 ring-inset' : ''} ${isTarget ? 'ring-4 ring-teal-400 ring-inset' : ''}`}
                      aria-label={piece ? `${piece.player} ${piece.king ? 'king' : 'man'}` : 'Empty square'}
                    >
                      {piece ? (
                        <span className={`flex h-8 w-8 items-center justify-center rounded-full border border-white/50 text-[10px] font-bold ${pieceClass(piece, pieceSkin)}`}>
                          {piece.king ? 'K' : ''}
                        </span>
                      ) : null}
                    </button>
                  )
                }))}
              </div>
            </div>

            <div className="space-y-3">
              <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                <p className="font-semibold text-slate-900">Game {trainingGame.game_id}</p>
                <p className="mt-1">Turn: {trainingGame.turn}</p>
                <p>Winner: {trainingGame.winner || 'none'}</p>
                <p>Mode: {trainingGame.mode}</p>
              </div>

              <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Coach feedback</p>
                {coachFeedback ? (
                  <>
                    <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-500">Latest evaluation • {coachFeedback.evaluated_player || 'unknown'} side</p>
                    <p className="mt-2 font-semibold text-slate-900">{coachFeedback.rating}: {coachFeedback.summary}</p>
                    <p className="mt-1 text-xs text-slate-500">Mode: {coachFeedback.analysis_mode} • Depth: {coachFeedback.search_depth}</p>
                    {coachFeedback.suggested_move ? (
                      <p className="mt-2">Suggested: {coachFeedback.suggested_move.from.join(', ')} → {coachFeedback.suggested_move.to.join(', ')}</p>
                    ) : null}
                    <ul className="mt-2 space-y-1">
                      {(coachFeedback.reasons || []).map((reason) => (
                        <li key={reason} className="rounded-lg bg-slate-50 px-2 py-1">{reason}</li>
                      ))}
                    </ul>

                    {coachHistory.length > 1 ? (
                      <div className="mt-3">
                        <button
                          type="button"
                          onClick={() => setShowOldEvaluations((current) => !current)}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                        >
                          {showOldEvaluations ? 'Hide older evaluations' : `Show older evaluations (${coachHistory.length - 1})`}
                        </button>

                        {showOldEvaluations ? (
                          <div className="mt-2 max-h-56 space-y-2 overflow-auto">
                            {coachHistory.slice(0, -1).reverse().map((entry) => (
                              <div key={entry.entry_id} className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs">
                                <p className="font-semibold text-slate-900">{entry.evaluated_player || 'unknown'} • {entry.rating}</p>
                                <p className="mt-1 text-slate-600">{entry.summary}</p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                ) : <p className="mt-2">Make a move to get analysis.</p>}
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">No active training session yet.</p>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Training tracks</p>
          <div className="mt-4 space-y-3">
            {trainingTracks.map((track) => (
              <div key={track.name} className="rounded-2xl bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-slate-900">{track.name}</p>
                  <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{track.status}</span>
                </div>
                <p className="mt-2 text-sm text-slate-600">{track.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Engine</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-900">Advanced coach status</h2>
          <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
            <p className="font-semibold text-slate-900">{engine ? engine.provider : 'Loading...'}</p>
            <p className="mt-1">Available: {engine ? String(engine.available) : '...'}</p>
            <p>Reason: {engine ? engine.reason : 'Checking provider status.'}</p>
            <p>Configured depth: {engine ? engine.configured_depth : '...'}</p>
          </div>

          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Recent games to review</p>
          <div className="mt-4 space-y-3">
            {recentMatches.map((match) => (
              <div key={match.id} className="rounded-2xl bg-slate-50 p-4 text-sm">
                <p className="font-semibold text-slate-900">{getMatchLabel(match)}</p>
                <p className="mt-1 text-slate-500">Mode: {match.mode} • Winner: {match.winner || 'Unknown'} • Moves: {match.total_moves}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
