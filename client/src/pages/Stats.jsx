import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

export default function Stats() {
  const [analytics, setAnalytics] = useState(null)
  const [cityLeaders, setCityLeaders] = useState([])
  const [rankedLeaders, setRankedLeaders] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true

    async function load() {
      try {
        const [analyticsResponse, citiesResponse, rankedResponse] = await Promise.all([
          fetch(`${API_BASE}/analytics/summary?days=14`),
          fetch(`${API_BASE}/leaderboard/cities?limit=8`),
          fetch(`${API_BASE}/leaderboard/ranked?limit=8`),
        ])
        const [analyticsData, citiesData, rankedData] = await Promise.all([
          analyticsResponse.json(),
          citiesResponse.json(),
          rankedResponse.json(),
        ])

        if (!isMounted) {
          return
        }

        setAnalytics(analyticsData)
        setCityLeaders(citiesData.cities || [])
        setRankedLeaders(rankedData.players || [])
      } catch {
        if (isMounted) {
          setError('Analytics endpoints are unavailable.')
        }
      }
    }

    load()
    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-gradient-to-br from-sky-100 via-white to-teal-50 p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700">Stats and analytics</p>
        <h1 className="mt-3 text-4xl font-bold text-slate-900">Platform metrics, funnel signals, and ladders</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          This page now pulls the actual analytics summary and leaderboard data already exposed by the server.
        </p>
      </section>

      {error ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p> : null}

      {analytics ? (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Events</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{analytics.total_events}</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Profiles</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{analytics.unique_profiles}</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Window</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{analytics.period_days}d</p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm xl:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Funnel</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {analytics ? Object.entries(analytics.funnel || {}).map(([key, value]) => (
              <div key={key} className="rounded-2xl bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{key.replaceAll('_', ' ')}</p>
                <p className="mt-2 text-xl font-semibold text-slate-900">{value}</p>
              </div>
            )) : <p className="text-sm text-slate-600">Loading funnel metrics...</p>}
          </div>

          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Event counts</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {analytics ? Object.entries(analytics.event_counts || {}).map(([key, value]) => (
              <div key={key} className="rounded-2xl bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{key.replaceAll('_', ' ')}</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{value}</p>
              </div>
            )) : null}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Daily activity</p>
          <div className="mt-4 space-y-3">
            {analytics?.daily?.length ? analytics.daily.map((day) => (
              <div key={day.date} className="rounded-2xl bg-slate-50 p-4 text-sm">
                <p className="font-semibold text-slate-900">{day.date}</p>
                <p className="mt-1 text-slate-500">{day.events} events • {day.unique_profiles} profiles</p>
              </div>
            )) : <p className="text-sm text-slate-600">No daily analytics returned yet.</p>}
          </div>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">City leaderboard</p>
          <div className="mt-4 space-y-3">
            {cityLeaders.map((entry) => (
              <div key={entry.city} className="flex items-center justify-between rounded-2xl bg-slate-50 p-4 text-sm">
                <span className="font-semibold text-slate-900">{entry.city}</span>
                <span className="text-slate-500">{entry.wins} wins / {entry.games} games</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Ranked ladder</p>
          <div className="mt-4 space-y-3">
            {rankedLeaders.map((player) => (
              <div key={player.profile_id} className="flex items-center justify-between rounded-2xl bg-slate-50 p-4 text-sm">
                <div>
                  <p className="font-semibold text-slate-900">{player.nickname}</p>
                  <p className="text-slate-500">{player.city || 'No city'} • {player.ranked_games} ranked games</p>
                </div>
                <span className="text-slate-700">ELO {player.elo_rating}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
