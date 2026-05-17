import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

function InfoCard({ eyebrow, title, children }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">{eyebrow}</p>
      <h2 className="mt-2 text-xl font-semibold text-slate-900">{title}</h2>
      <div className="mt-4 text-sm text-slate-600">{children}</div>
    </section>
  )
}

function getMatchLabel(match) {
  const whiteName = match?.players?.white?.nickname || 'White'
  const redName = match?.players?.red?.nickname || 'Red'
  return `${whiteName} vs ${redName}`
}

export default function Home({ auth }) {
  const [health, setHealth] = useState(null)
  const [engine, setEngine] = useState(null)
  const [recentMatches, setRecentMatches] = useState([])
  const [cityLeaders, setCityLeaders] = useState([])
  const [rankedLeaders, setRankedLeaders] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true

    async function load() {
      try {
        const [healthResponse, engineResponse, matchesResponse, citiesResponse, rankedResponse] = await Promise.all([
          fetch(`${API_BASE}/health`),
          fetch(`${API_BASE}/engine/status`),
          fetch(`${API_BASE}/matches/recent?limit=5`),
          fetch(`${API_BASE}/leaderboard/cities?limit=5`),
          fetch(`${API_BASE}/leaderboard/ranked?limit=5`),
        ])

        const [healthData, engineData, matchesData, citiesData, rankedData] = await Promise.all([
          healthResponse.json(),
          engineResponse.json(),
          matchesResponse.json(),
          citiesResponse.json(),
          rankedResponse.json(),
        ])

        if (!isMounted) {
          return
        }

        setHealth(healthData)
        setEngine(engineData)
        setRecentMatches(matchesData.matches || [])
        setCityLeaders(citiesData.cities || [])
        setRankedLeaders(rankedData.players || [])
      } catch {
        if (isMounted) {
          setError('Live platform data is unavailable. Check that the API server is running on port 8000.')
        }
      }
    }

    load()
    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="space-y-8">
      <section className="rounded-[2rem] bg-gradient-to-br from-slate-950 via-teal-900 to-emerald-700 p-8 text-white shadow-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-emerald-200">Match Search</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-bold sm:text-5xl">Play, train, review, and grow from one checkers hub.</h1>
        <p className="mt-4 max-w-2xl text-sm text-emerald-50/90 sm:text-base">
          This product is already more than a board: ranked ladder, daily puzzles, AI training, replay review, analytics, and social features are all wired on the backend. The home page now surfaces that work instead of a placeholder sentence.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/training" className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-100">
            Start training
          </Link>
          <Link to="/puzzles" className="rounded-full border border-white/30 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10">
            Solve puzzles
          </Link>
          <Link to="/stats" className="rounded-full border border-white/30 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10">
            See analytics
          </Link>
          {!auth.isAuthenticated ? (
            <button
              type="button"
              onClick={auth.openAuth}
              className="rounded-full border border-amber-300 bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-amber-200"
            >
              Sign in
            </button>
          ) : null}
        </div>
      </section>

      {error ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p> : null}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <InfoCard eyebrow="Live status" title="Platform heartbeat">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">API</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{health ? `${health.service}: ${health.status}` : 'Loading...'}</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Engine</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">{engine ? `${engine.provider} ${engine.available ? 'available' : 'fallback'}` : 'Loading...'}</p>
              <p className="mt-1 text-xs text-slate-500">{engine ? engine.reason : 'Checking advanced engine status.'}</p>
            </div>
          </div>
        </InfoCard>

        <InfoCard eyebrow="Account" title={auth.isAuthenticated ? `Signed in as ${auth.username}` : 'Guest session'}>
          <p>
            {auth.isAuthenticated
              ? 'Open Profile and Social to see your stored profile, sessions, missions, achievements, and friends.'
              : 'Sign in to unlock your profile, friends list, session controls, and retention surfaces.'}
          </p>
        </InfoCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <InfoCard eyebrow="Recent games" title="Replay-ready matches">
          {recentMatches.length ? (
            <ul className="space-y-3">
              {recentMatches.map((match) => (
                <li key={match.id} className="rounded-2xl bg-slate-50 p-4">
                  <p className="font-semibold text-slate-900">{getMatchLabel(match)}</p>
                  <p className="mt-1 text-xs text-slate-500">Winner: {match.winner || 'In progress'} • Mode: {match.mode} • Moves: {match.total_moves}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p>No recent matches returned yet.</p>
          )}
        </InfoCard>

        <InfoCard eyebrow="City ladder" title="Top communities">
          {cityLeaders.length ? (
            <ul className="space-y-3">
              {cityLeaders.map((city) => (
                <li key={city.city} className="flex items-center justify-between rounded-2xl bg-slate-50 p-4">
                  <span className="font-semibold text-slate-900">{city.city}</span>
                  <span className="text-xs text-slate-500">{city.wins} wins / {city.games} games</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>Leaderboard data will appear here once games are recorded.</p>
          )}
        </InfoCard>

        <InfoCard eyebrow="Ranked" title="Ladder leaders">
          {rankedLeaders.length ? (
            <ul className="space-y-3">
              {rankedLeaders.map((player) => (
                <li key={player.profile_id} className="flex items-center justify-between rounded-2xl bg-slate-50 p-4">
                  <span className="font-semibold text-slate-900">{player.nickname}</span>
                  <span className="text-xs text-slate-500">ELO {player.elo_rating}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>Ranked placements will populate here after placement matches are completed.</p>
          )}
        </InfoCard>
      </div>
    </div>
  )
}
