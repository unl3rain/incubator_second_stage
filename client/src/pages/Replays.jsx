import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

function getMatchLabel(match) {
  const whiteName = match?.players?.white?.nickname || 'White'
  const redName = match?.players?.red?.nickname || 'Red'
  return `${whiteName} vs ${redName}`
}

export default function Replays() {
  const [matches, setMatches] = useState([])
  const [selectedMatch, setSelectedMatch] = useState(null)
  const [selectedReplay, setSelectedReplay] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [stateIndex, setStateIndex] = useState(0)
  const [loadingReplayId, setLoadingReplayId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true

    async function loadMatches() {
      try {
        const response = await fetch(`${API_BASE}/matches/recent?limit=8`)
        const data = await response.json()
        if (isMounted) {
          setMatches(data.matches || [])
        }
      } catch {
        if (isMounted) {
          setError('Replay list is unavailable.')
        }
      }
    }

    loadMatches()
    return () => {
      isMounted = false
    }
  }, [])

  const loadReplay = async (match) => {
    setLoadingReplayId(match.id)
    setError('')

    try {
      const response = await fetch(`${API_BASE}/matches/${match.id}`)
      const data = await response.json()
      if (!response.ok) {
        setError(data.detail || 'Could not load replay.')
        return
      }

      let accuracyData = null
      try {
        const accuracyResponse = await fetch(`${API_BASE}/games/${encodeURIComponent(match.game_id)}/accuracy`)
        const payload = await accuracyResponse.json().catch(() => ({}))
        if (accuracyResponse.ok) {
          accuracyData = payload
        }
      } catch {
        // Accuracy may be unavailable for old or incompatible games.
      }

      setSelectedMatch(match)
      setSelectedReplay(data)
      setAccuracy(accuracyData)
      setStateIndex(Math.max(0, (data.states?.length || 1) - 1))
    } catch {
      setError('Could not load replay.')
    } finally {
      setLoadingReplayId('')
    }
  }

  const currentState = selectedReplay?.states?.[stateIndex] || null

  const boardSquareClass = (row, col) => ((row + col) % 2 === 1 ? 'bg-emerald-900' : 'bg-amber-100')

  const pieceClass = (piece) => (piece?.player === 'white'
    ? 'bg-slate-200 text-slate-900'
    : 'bg-rose-700 text-white')

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Recent matches</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Replay archive</h1>
        <p className="mt-3 text-sm text-slate-600">Load a completed match to inspect the archived board states returned by the server.</p>
        {error ? <p className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p> : null}
        <div className="mt-6 space-y-3">
          {matches.map((match) => (
            <button
              key={match.id}
              type="button"
              onClick={() => loadReplay(match)}
              className="block w-full rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left transition hover:border-teal-300 hover:bg-white"
            >
              <p className="font-semibold text-slate-900">{getMatchLabel(match)}</p>
              <p className="mt-1 text-xs text-slate-500">Winner: {match.winner || 'Unknown'} • Moves: {match.total_moves} • {loadingReplayId === match.id ? 'Loading...' : 'Open replay'}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Selected replay</p>
        {selectedReplay && selectedMatch ? (
          <>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900">{getMatchLabel(selectedMatch)}</h2>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Winner</p>
                <p className="mt-2 font-semibold text-slate-900">{selectedReplay.match.winner || 'None'}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Mode</p>
                <p className="mt-2 font-semibold text-slate-900">{selectedReplay.match.mode}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">States</p>
                <p className="mt-2 font-semibold text-slate-900">{selectedReplay.states.length}</p>
              </div>
            </div>

            {accuracy ? (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Accuracy summary</p>
                <p className="mt-2 font-semibold text-slate-900">Overall: {Math.round(accuracy.accuracy_percent)}%</p>
                <p className="mt-1">Best: {accuracy.bests} • Good: {accuracy.goods} • OK: {accuracy.oks}</p>
                <p>Mistakes: {accuracy.mistakes} • Blunders: {accuracy.blunders}</p>
              </div>
            ) : null}

            <div className="mt-6 space-y-3">
              {currentState ? (
                <>
                  <div className="flex items-center justify-between rounded-2xl border border-slate-200 p-4 text-sm">
                    <div>
                      <p className="font-semibold text-slate-900">State {stateIndex + 1} of {selectedReplay.states.length}</p>
                      <p className="mt-1 text-slate-500">Move index {currentState.move_index} • Turn: {currentState.turn} • Winner: {currentState.winner || 'None'}</p>
                      {currentState.last_move ? (
                        <p className="mt-2 text-slate-600">
                          Last move: {currentState.last_move.player} from {currentState.last_move.from.join(', ')} to {currentState.last_move.to.join(', ')}
                        </p>
                      ) : (
                        <p className="mt-2 text-slate-600">Initial position.</p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setStateIndex((current) => Math.max(0, current - 1))} disabled={stateIndex <= 0} className="rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 disabled:opacity-60">Prev</button>
                      <button type="button" onClick={() => setStateIndex((current) => Math.min(selectedReplay.states.length - 1, current + 1))} disabled={stateIndex >= selectedReplay.states.length - 1} className="rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 disabled:opacity-60">Next</button>
                    </div>
                  </div>

                  <input
                    type="range"
                    min={0}
                    max={Math.max(0, selectedReplay.states.length - 1)}
                    value={stateIndex}
                    onChange={(event) => setStateIndex(Number(event.target.value))}
                    className="w-full"
                  />

                  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="grid grid-cols-8 gap-0">
                      {currentState.board.map((row, rowIndex) => row.map((piece, colIndex) => (
                        <div key={`replay-${rowIndex}-${colIndex}`} className={`relative aspect-square flex items-center justify-center ${boardSquareClass(rowIndex, colIndex)}`}>
                          {piece ? (
                            <span className={`flex h-8 w-8 items-center justify-center rounded-full border border-white/50 text-[10px] font-bold ${pieceClass(piece)}`}>
                              {piece.king ? 'K' : ''}
                            </span>
                          ) : null}
                        </div>
                      )))}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </>
        ) : (
          <div className="mt-6 rounded-2xl bg-slate-50 p-6 text-sm text-slate-600">
            Pick a recent match to inspect the archived replay states and metadata.
          </div>
        )}
      </section>
    </div>
  )
}
