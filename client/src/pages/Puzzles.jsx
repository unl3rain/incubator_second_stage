import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

function boardSquareClass(row, col, boardSkin) {
  const dark = (row + col) % 2 === 1
  if (boardSkin === 'carbon') {
    return dark ? 'bg-slate-900 text-white' : 'bg-slate-300 text-slate-900'
  }
  if (boardSkin === 'sunset') {
    return dark ? 'bg-orange-900 text-white' : 'bg-amber-200 text-amber-950'
  }
  if (boardSkin === 'ocean') {
    return dark ? 'bg-teal-950 text-white' : 'bg-cyan-200 text-slate-900'
  }
  if (boardSkin === 'ruby') {
    return dark ? 'bg-rose-950 text-white' : 'bg-pink-200 text-rose-900'
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
    ? 'bg-slate-200 text-slate-900'
    : 'bg-rose-700 text-white'
}

export default function Puzzles({ auth }) {
  const [dailyPuzzle, setDailyPuzzle] = useState(null)
  const [selectedFrom, setSelectedFrom] = useState(null)
  const [selectedTo, setSelectedTo] = useState(null)
  const [rushState, setRushState] = useState(null)
  const [rushSelectedFrom, setRushSelectedFrom] = useState(null)
  const [rushSelectedTo, setRushSelectedTo] = useState(null)
  const [loadingRush, setLoadingRush] = useState(false)
  const [submittingRush, setSubmittingRush] = useState(false)
  const [finishingRush, setFinishingRush] = useState(false)
  const [submittingPuzzle, setSubmittingPuzzle] = useState(false)
  const [message, setMessage] = useState('')
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

  useEffect(() => {
    let isMounted = true

    async function loadPuzzle() {
      try {
        const query = auth.profileId ? `?profile_id=${encodeURIComponent(auth.profileId)}` : ''
        const response = await fetch(`${API_BASE}/puzzles/daily${query}`)
        const data = await response.json()
        if (isMounted) {
          setDailyPuzzle(data)
          setSelectedFrom(null)
          setSelectedTo(null)
        }
      } catch {
        if (isMounted) {
          setMessage('Daily puzzle is unavailable right now.')
        }
      }
    }

    loadPuzzle()
    return () => {
      isMounted = false
    }
  }, [auth.profileId])

  const handlePuzzleSquareClick = (row, col) => {
    if (!dailyPuzzle || dailyPuzzle.solved_today) {
      return
    }

    const piece = dailyPuzzle.board?.[row]?.[col]
    if (!selectedFrom) {
      if (piece && piece.player === dailyPuzzle.turn) {
        setSelectedFrom([row, col])
      }
      return
    }

    setSelectedTo([row, col])
  }

  const submitDailyPuzzle = async () => {
    if (!dailyPuzzle || !auth.profileId || !selectedFrom || !selectedTo) {
      return
    }

    setSubmittingPuzzle(true)
    setMessage('')

    try {
      const response = await fetch(`${API_BASE}/puzzles/daily/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: auth.profileId,
          puzzle_date: dailyPuzzle.puzzle_date,
          from: selectedFrom,
          to: selectedTo,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setMessage(data.message || 'Puzzle submitted.')
      await loadDailyPuzzle()
    } catch (error) {
      setMessage(`Could not submit puzzle (${error.message})`)
    } finally {
      setSubmittingPuzzle(false)
    }
  }

  const loadDailyPuzzle = async () => {
    const query = auth.profileId ? `?profile_id=${encodeURIComponent(auth.profileId)}` : ''
    const response = await fetch(`${API_BASE}/puzzles/daily${query}`)
    const data = await response.json().catch(() => ({}))
    if (response.ok) {
      setDailyPuzzle(data)
      setSelectedFrom(null)
      setSelectedTo(null)
    }
  }

  const startRush = async () => {
    setLoadingRush(true)
    setMessage('')
    try {
      const response = await fetch(`${API_BASE}/puzzle-rush/start?time_seconds=60&difficulty=mixed`, {
        method: 'POST',
      })
      const data = await response.json()
      if (!response.ok) {
        setMessage(data.detail || 'Could not start Puzzle Rush.')
        return
      }

      setRushState(data)
      setRushSelectedFrom(null)
      setRushSelectedTo(null)
    } catch {
      setMessage('Could not start Puzzle Rush.')
    } finally {
      setLoadingRush(false)
    }
  }

  const currentRushPuzzle = rushState?.next_puzzle || rushState?.puzzles?.[0] || null

  const handleRushSquareClick = (row, col) => {
    if (!currentRushPuzzle || finishingRush || submittingRush) {
      return
    }

    const piece = currentRushPuzzle.board?.[row]?.[col]
    if (!rushSelectedFrom) {
      if (piece && piece.player === currentRushPuzzle.player_to_move) {
        setRushSelectedFrom([row, col])
      }
      return
    }

    setRushSelectedTo([row, col])
  }

  const submitRushMove = async () => {
    if (!rushState?.session_id || !currentRushPuzzle?.puzzle_id || !rushSelectedFrom || !rushSelectedTo) {
      return
    }

    setSubmittingRush(true)
    setMessage('')

    try {
      const response = await fetch(`${API_BASE}/puzzle-rush/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: rushState.session_id,
          puzzle_id: currentRushPuzzle.puzzle_id,
          moves: [{ from: rushSelectedFrom, to: rushSelectedTo }],
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setRushState((current) => ({
        ...(current || {}),
        next_puzzle: data.next_puzzle || null,
        total_score: data.total_score,
        puzzles_solved: data.puzzles_solved,
        time_remaining: data.time_remaining,
      }))
      setRushSelectedFrom(null)
      setRushSelectedTo(null)
      setMessage(data.correct ? 'Correct Puzzle Rush move.' : 'Move submitted. Continue to the next puzzle.')
    } catch (error) {
      setMessage(`Could not submit rush move (${error.message})`)
    } finally {
      setSubmittingRush(false)
    }
  }

  const finishRush = async () => {
    if (!rushState?.session_id) {
      return
    }

    setFinishingRush(true)
    setMessage('')

    try {
      const response = await fetch(`${API_BASE}/puzzle-rush/finish?session_id=${encodeURIComponent(rushState.session_id)}`, {
        method: 'POST',
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setMessage(`Puzzle Rush finished. Score ${data.final_score}, solved ${data.puzzles_solved}.`)
      setRushState(null)
      setRushSelectedFrom(null)
      setRushSelectedTo(null)
    } catch (error) {
      setMessage(`Could not finish Puzzle Rush (${error.message})`)
    } finally {
      setFinishingRush(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-gradient-to-br from-amber-100 via-orange-50 to-white p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-700">Puzzles</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">Daily challenge and speed training</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          The backend already supports both daily puzzle tracking and Puzzle Rush sessions. This page now surfaces that live data instead of a stub.
        </p>
      </section>

      {message ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{message}</p> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Daily puzzle</p>
          {dailyPuzzle ? (
            <>
              <h2 className="mt-2 text-2xl font-semibold text-slate-900">{dailyPuzzle.title}</h2>
              <p className="mt-3 text-sm text-slate-600">{dailyPuzzle.hint}</p>
              <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div className="grid grid-cols-8 gap-0">
                  {dailyPuzzle.board.map((row, rowIndex) => row.map((piece, colIndex) => {
                    const isSource = selectedFrom && selectedFrom[0] === rowIndex && selectedFrom[1] === colIndex
                    const isTarget = selectedTo && selectedTo[0] === rowIndex && selectedTo[1] === colIndex
                    return (
                      <button
                        key={`${rowIndex}-${colIndex}`}
                        type="button"
                        onClick={() => handlePuzzleSquareClick(rowIndex, colIndex)}
                        className={`relative aspect-square flex items-center justify-center ${boardSquareClass(rowIndex, colIndex, boardSkin)} ${isSource ? 'ring-4 ring-amber-300 ring-inset' : ''} ${isTarget ? 'ring-4 ring-teal-400 ring-inset' : ''}`}
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
              <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="text-slate-500">Difficulty</dt>
                  <dd className="mt-1 font-semibold text-slate-900">{dailyPuzzle.difficulty}</dd>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="text-slate-500">Turn</dt>
                  <dd className="mt-1 font-semibold text-slate-900">{dailyPuzzle.turn}</dd>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="text-slate-500">Attempts today</dt>
                  <dd className="mt-1 font-semibold text-slate-900">{dailyPuzzle.attempts_today}</dd>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="text-slate-500">Streak</dt>
                  <dd className="mt-1 font-semibold text-slate-900">{dailyPuzzle.streak}</dd>
                </div>
              </dl>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={submitDailyPuzzle}
                  disabled={submittingPuzzle || !selectedFrom || !selectedTo || dailyPuzzle.solved_today}
                  className="rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
                >
                  {dailyPuzzle.solved_today ? 'Already solved today' : submittingPuzzle ? 'Submitting...' : 'Submit move'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedFrom(null)
                    setSelectedTo(null)
                  }}
                  className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  Clear selection
                </button>
              </div>
            </>
          ) : (
            <p className="mt-4 text-sm text-slate-600">Loading the daily puzzle...</p>
          )}
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Puzzle Rush</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-900">One-minute sprint</h2>
          <p className="mt-3 text-sm text-slate-600">Start a live rush session to confirm the backend session flow is active.</p>
          <button
            type="button"
            onClick={startRush}
            disabled={loadingRush}
            className="mt-6 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
          >
            {loadingRush ? 'Starting...' : 'Start Puzzle Rush'}
          </button>
          {rushState ? (
            <div className="mt-6 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
              <p className="font-semibold text-slate-900">Session {rushState.session_id}</p>
              <p className="mt-2">Difficulty: {rushState.difficulty}</p>
              <p>Time limit: {rushState.time_limit_seconds} seconds</p>
              <p>Score: {rushState.total_score || 0} • Solved: {rushState.puzzles_solved || 0}</p>
              <p>Time remaining: {rushState.time_remaining ?? rushState.time_limit_seconds} seconds</p>
              <p className="mt-2 font-semibold text-slate-900">Current puzzle: {currentRushPuzzle?.title || 'Unavailable'}</p>
              {currentRushPuzzle ? (
                <>
                  <p className="mt-2 text-xs text-slate-500">{currentRushPuzzle.hint}</p>
                  <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white p-2">
                    <div className="grid grid-cols-8 gap-0">
                      {currentRushPuzzle.board.map((row, rowIndex) => row.map((piece, colIndex) => {
                        const isSource = rushSelectedFrom && rushSelectedFrom[0] === rowIndex && rushSelectedFrom[1] === colIndex
                        const isTarget = rushSelectedTo && rushSelectedTo[0] === rowIndex && rushSelectedTo[1] === colIndex
                        return (
                          <button
                            key={`rush-${rowIndex}-${colIndex}`}
                            type="button"
                            onClick={() => handleRushSquareClick(rowIndex, colIndex)}
                            className={`relative aspect-square flex items-center justify-center ${boardSquareClass(rowIndex, colIndex, boardSkin)} ${isSource ? 'ring-4 ring-amber-300 ring-inset' : ''} ${isTarget ? 'ring-4 ring-teal-400 ring-inset' : ''}`}
                            aria-label={piece ? `${piece.player} ${piece.king ? 'king' : 'man'}` : 'Empty square'}
                          >
                            {piece ? (
                              <span className={`flex h-6 w-6 items-center justify-center rounded-full border border-white/50 text-[9px] font-bold ${pieceClass(piece, pieceSkin)}`}>
                                {piece.king ? 'K' : ''}
                              </span>
                            ) : null}
                          </button>
                        )
                      }))}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" onClick={submitRushMove} disabled={submittingRush || !rushSelectedFrom || !rushSelectedTo} className="rounded-lg bg-teal-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">
                      {submittingRush ? 'Submitting...' : 'Submit rush move'}
                    </button>
                    <button type="button" onClick={finishRush} disabled={finishingRush} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">
                      {finishingRush ? 'Finishing...' : 'Finish session'}
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}
