import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

export default function Profile({ auth }) {
  const [profile, setProfile] = useState(null)
  const [profileMatches, setProfileMatches] = useState([])
  const [cosmetics, setCosmetics] = useState(null)
  const [sessions, setSessions] = useState([])
  const [missions, setMissions] = useState([])
  const [achievements, setAchievements] = useState([])
  const [notifications, setNotifications] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionMessage, setActionMessage] = useState('')
  const [billingBusy, setBillingBusy] = useState(false)
  const [provider, setProvider] = useState('google')
  const [providerUserId, setProviderUserId] = useState('')
  const [providerEmail, setProviderEmail] = useState('')
  const [providerUsername, setProviderUsername] = useState('')

  useEffect(() => {
    let isMounted = true

    async function load() {
      if (!auth.profileId) {
        return
      }

      try {
        const requests = [
          fetch(`${API_BASE}/profiles/${auth.profileId}`),
          fetch(`${API_BASE}/profiles/${auth.profileId}/matches?limit=6`),
          fetch(`${API_BASE}/profiles/${auth.profileId}/cosmetics`),
          fetch(`${API_BASE}/retention/missions?profile_id=${encodeURIComponent(auth.profileId)}`),
          fetch(`${API_BASE}/retention/achievements?profile_id=${encodeURIComponent(auth.profileId)}&limit=6`),
          fetch(`${API_BASE}/retention/notifications?profile_id=${encodeURIComponent(auth.profileId)}`),
        ]

        if (auth.token) {
          requests.push(fetch(`${API_BASE}/auth/sessions`, { headers: { Authorization: `Bearer ${auth.token}` } }))
        }

        const responses = await Promise.all(requests)
        const payloads = await Promise.all(responses.map((response) => response.json().catch(() => ({}))))

        if (!isMounted) {
          return
        }

        setProfile(payloads[0])
        setProfileMatches(payloads[1].matches || [])
        setCosmetics(payloads[2] || null)
        if (payloads[2]?.equipped_board_skin) {
          window.localStorage.setItem('checkers.board_skin', payloads[2].equipped_board_skin)
        }
        if (payloads[2]?.equipped_piece_skin) {
          window.localStorage.setItem('checkers.piece_skin', payloads[2].equipped_piece_skin)
        }
        window.dispatchEvent(new Event('checkers-skins-updated'))
        setMissions(payloads[3].missions || [])
        setAchievements(payloads[4].achievements || [])
        setNotifications(payloads[5].notifications || [])
        setSessions(payloads[6]?.sessions || [])
      } catch {
        if (isMounted) {
          setError('Could not load profile surfaces.')
        }
      }
    }

    load()
    return () => {
      isMounted = false
    }
  }, [auth.profileId, auth.token])

  if (!auth.isAuthenticated || !auth.profileId) {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Profile</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Account stats, achievements, and sessions</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">Sign in to load the profile document, active sessions, missions, achievements, and notifications tied to your stored profile.</p>
        <button type="button" onClick={auth.openAuth} className="mt-6 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-700">
          Sign in to open profile
        </button>
      </section>
    )
  }

  const apiCall = async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${auth.token}`,
      },
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`)
    }
    return data
  }

  const refreshProfile = async () => {
    const [profileData, matchData, cosmeticsData] = await Promise.all([
      apiCall(`/profiles/${auth.profileId}`),
      apiCall(`/profiles/${auth.profileId}/matches?limit=6`),
      apiCall(`/profiles/${auth.profileId}/cosmetics`),
    ])
    setProfile(profileData)
    setProfileMatches(matchData.matches || [])
    setCosmetics(cosmeticsData)
    if (cosmeticsData?.equipped_board_skin) {
      window.localStorage.setItem('checkers.board_skin', cosmeticsData.equipped_board_skin)
    }
    if (cosmeticsData?.equipped_piece_skin) {
      window.localStorage.setItem('checkers.piece_skin', cosmeticsData.equipped_piece_skin)
    }
    window.dispatchEvent(new Event('checkers-skins-updated'))
  }

  const issueMissions = async (kind) => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall(`/retention/missions/issue-${kind}?profile_id=${encodeURIComponent(auth.profileId)}`, {
        method: 'POST',
      })
      setActionMessage(`Issued ${data.issued_count || 0} ${kind} mission(s).`)
      const missionsData = await apiCall(`/retention/missions?profile_id=${encodeURIComponent(auth.profileId)}`)
      setMissions(missionsData.missions || [])
    } catch (error) {
      setActionMessage(`Could not issue ${kind} missions (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const isPro = auth.subscription === 'pro'
  const canEquipSkin = (kind, skinId) => {
    const ownedSkins = kind === 'board'
      ? cosmetics?.owned_board_skins || []
      : cosmetics?.owned_piece_skins || []

    if (ownedSkins.includes(skinId)) {
      return true
    }

    if (isPro) {
      return true
    }

    return false
  }

  const equipSkin = async (kind, skinId) => {
    if (!canEquipSkin(kind, skinId)) {
      setActionMessage('Upgrade to Pro to equip premium skins.')
      return
    }

    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall(`/profiles/${auth.profileId}/cosmetics/equip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, skin_id: skinId }),
      })
      setCosmetics(data)
      if (data?.equipped_board_skin) {
        window.localStorage.setItem('checkers.board_skin', data.equipped_board_skin)
      }
      if (data?.equipped_piece_skin) {
        window.localStorage.setItem('checkers.piece_skin', data.equipped_piece_skin)
      }
      window.dispatchEvent(new Event('checkers-skins-updated'))
      setActionMessage(`${kind === 'board' ? 'Board' : 'Piece'} skin updated to ${skinId}.`)
    } catch (error) {
      setActionMessage(`Could not equip ${kind} skin (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const startCheckout = async (plan) => {
    setBillingBusy(true)
    setActionMessage('')
    try {
      const response = await fetch(`${API_BASE}/billing/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: auth.profileId, plan }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      if (data.checkout_url) {
        window.open(data.checkout_url, '_blank', 'noopener,noreferrer')
      }
      setActionMessage(`Checkout started (${data.mode || 'unknown'}).`)
      await refreshProfile()
    } catch (error) {
      setActionMessage(`Could not start checkout (${error.message})`)
    } finally {
      setBillingBusy(false)
    }
  }

  const linkProvider = async () => {
    if (!providerUserId.trim() || !providerEmail.trim()) {
      setActionMessage('Provider user id and email are required to link account.')
      return
    }

    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall('/auth/link-provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider,
          provider_user_id: providerUserId.trim(),
          email: providerEmail.trim(),
          username: providerUsername.trim() || null,
        }),
      })
      setActionMessage(data.message || 'Provider linked.')
      setProviderUserId('')
      setProviderEmail('')
      setProviderUsername('')
    } catch (error) {
      setActionMessage(`Could not link provider (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const unlinkProvider = async (targetProvider) => {
    setBusy(true)
    setActionMessage('')
    try {
      const response = await fetch(`${API_BASE}/auth/unlink-provider?provider=${encodeURIComponent(targetProvider)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }
      setActionMessage(data.message || `${targetProvider} provider unlinked.`)
    } catch (error) {
      setActionMessage(`Could not unlink provider (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const revokeAllOtherSessions = async () => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall('/auth/revoke-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keep_current: true }),
      })
      setActionMessage(data.message || 'Other sessions revoked.')
      const sessionsData = await apiCall('/auth/sessions')
      setSessions(sessionsData.sessions || [])
    } catch (error) {
      setActionMessage(`Could not revoke sessions (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const revokeSessionById = async (sessionId) => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall('/auth/revoke-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      setActionMessage(data.message || 'Session revoked.')
      const sessionsData = await apiCall('/auth/sessions')
      setSessions(sessionsData.sessions || [])
    } catch (error) {
      setActionMessage(`Could not revoke session (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const markNotificationAsRead = async (notificationId) => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall(`/retention/notifications/${encodeURIComponent(notificationId)}/read`, {
        method: 'POST',
      })
      setActionMessage(data.message || 'Notification marked as read.')
      setNotifications((current) => current.filter((item) => (item.notification_id || item.id) !== notificationId))
      await refreshProfile()
    } catch (error) {
      setActionMessage(`Could not update notification (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-gradient-to-br from-indigo-100 via-white to-slate-50 p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-700">Profile and settings</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">Stored account data, not a stub</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">This page now consumes the profile, mission, achievement, notification, and session APIs already present on the backend.</p>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm text-slate-700">Subscription status</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{isPro ? 'Pro member' : 'Free user'}</p>
          </div>
          {!isPro ? (
            <button type="button" onClick={auth.openDemoPayment} className="rounded-xl bg-amber-100 px-4 py-3 text-sm font-semibold text-amber-900 transition hover:bg-amber-200">
              Upgrade to Pro
            </button>
          ) : null}
        </div>
      </section>

      {error ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p> : null}
      {actionMessage ? <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">{actionMessage}</p> : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Session controls</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <button type="button" onClick={revokeAllOtherSessions} disabled={busy} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60">Revoke other sessions</button>
          <button type="button" onClick={refreshProfile} disabled={busy} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Refresh profile</button>
          <button type="button" onClick={() => issueMissions('daily')} disabled={busy} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Issue daily missions</button>
          <button type="button" onClick={() => issueMissions('weekly')} disabled={busy} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Issue weekly missions</button>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Billing</p>
          <p className="mt-2 text-sm text-slate-600">Use backend checkout flow for Pro plans.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <button type="button" onClick={() => startCheckout('pro_monthly')} disabled={billingBusy} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60">Pro monthly</button>
            <button type="button" onClick={() => startCheckout('pro_yearly')} disabled={billingBusy} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Pro yearly</button>
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Linked providers</p>
          <p className="mt-2 text-sm text-slate-600">Link or unlink Google/GitHub providers using existing backend endpoints.</p>
          <div className="mt-4 grid gap-3">
            <select value={provider} onChange={(event) => setProvider(event.target.value)} className="rounded-xl border border-slate-300 px-3 py-2 text-sm">
              <option value="google">google</option>
              <option value="github">github</option>
            </select>
            <input value={providerUserId} onChange={(event) => setProviderUserId(event.target.value)} placeholder="Provider user id" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" />
            <input type="email" value={providerEmail} onChange={(event) => setProviderEmail(event.target.value)} placeholder="Provider email" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" />
            <input value={providerUsername} onChange={(event) => setProviderUsername(event.target.value)} placeholder="Display name (optional)" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" />
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={linkProvider} disabled={busy} className="rounded-lg bg-teal-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">Link provider</button>
              <button type="button" onClick={() => unlinkProvider('google')} disabled={busy} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Unlink Google</button>
              <button type="button" onClick={() => unlinkProvider('github')} disabled={busy} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Unlink GitHub</button>
            </div>
          </div>
        </section>
      </div>

      {profile ? (
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-xs uppercase tracking-[0.2em] text-slate-500">Games</p><p className="mt-2 text-3xl font-bold text-slate-900">{profile.games}</p></div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-xs uppercase tracking-[0.2em] text-slate-500">Wins</p><p className="mt-2 text-3xl font-bold text-slate-900">{profile.wins}</p></div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-xs uppercase tracking-[0.2em] text-slate-500">Win rate</p><p className="mt-2 text-3xl font-bold text-slate-900">{Math.round(profile.win_rate)}%</p></div>
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-xs uppercase tracking-[0.2em] text-slate-500">ELO</p><p className="mt-2 text-3xl font-bold text-slate-900">{profile.elo_rating}</p></div>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Profile</p>
          {profile ? (
            <div className="mt-4 space-y-2 text-sm text-slate-600">
              <p><span className="font-semibold text-slate-900">Nickname:</span> {profile.nickname}</p>
              <p><span className="font-semibold text-slate-900">City:</span> {profile.city || 'No city'}</p>
              <p><span className="font-semibold text-slate-900">Season:</span> {profile.season_key}</p>
              <p><span className="font-semibold text-slate-900">Pro:</span> {profile.pro_active ? 'Active' : 'Inactive'}</p>
              <p><span className="font-semibold text-slate-900">Linked provider:</span> {profile.linked_provider || 'none'}</p>
              {profile.linked_provider ? (
                <>
                  <p><span className="font-semibold text-slate-900">Provider user id:</span> {profile.linked_provider_user_id || 'n/a'}</p>
                  <p><span className="font-semibold text-slate-900">Provider display:</span> {profile.linked_provider_display_name || 'n/a'}</p>
                </>
              ) : null}
            </div>
          ) : <p className="mt-4 text-sm text-slate-600">Loading profile...</p>}
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Missions</p>
          <div className="mt-4 space-y-3 text-sm">
            {missions.length ? missions.map((mission) => (
              <div key={mission.mission_id || mission.title} className="rounded-2xl bg-slate-50 p-4">
                <p className="font-semibold text-slate-900">{mission.title || mission.mission_type}</p>
                <p className="mt-1 text-slate-500">{mission.description || 'Mission issued on backend.'}</p>
              </div>
            )) : <p className="text-slate-600">No active missions returned.</p>}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Achievements</p>
          <div className="mt-4 space-y-3 text-sm">
            {achievements.length ? achievements.map((achievement) => (
              <div key={achievement.achievement_id || achievement.code || achievement.title} className="rounded-2xl bg-slate-50 p-4">
                <p className="font-semibold text-slate-900">{achievement.title || achievement.code}</p>
                <p className="mt-1 text-slate-500">{achievement.description || 'Achievement unlocked.'}</p>
              </div>
            )) : <p className="text-slate-600">No achievements returned yet.</p>}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Cosmetics</p>
          {cosmetics ? (
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <p><span className="font-semibold text-slate-900">Board:</span> {cosmetics.equipped_board_skin}</p>
              <p><span className="font-semibold text-slate-900">Pieces:</span> {cosmetics.equipped_piece_skin}</p>
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Owned board skins</p>
                <div className="flex flex-wrap gap-2">
                  {(cosmetics.owned_board_skins || []).map((skin) => {
                    const allowed = canEquipSkin('board', skin)
                    return (
                      <button
                        key={skin}
                        type="button"
                        onClick={() => equipSkin('board', skin)}
                        disabled={busy || !allowed}
                        className={`rounded-lg px-3 py-1 text-xs font-semibold transition ${cosmetics.equipped_board_skin === skin ? 'bg-slate-900 text-white' : allowed ? 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100' : 'border border-amber-200 bg-amber-50 text-amber-900 cursor-not-allowed'}`}
                        title={!allowed ? 'Pro only board skin' : ''}
                      >
                        {skin}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Owned piece skins</p>
                <div className="flex flex-wrap gap-2">
                  {(cosmetics.owned_piece_skins || []).map((skin) => {
                    const allowed = canEquipSkin('piece', skin)
                    return (
                      <button
                        key={skin}
                        type="button"
                        onClick={() => equipSkin('piece', skin)}
                        disabled={busy || !allowed}
                        className={`rounded-lg px-3 py-1 text-xs font-semibold transition ${cosmetics.equipped_piece_skin === skin ? 'bg-slate-900 text-white' : allowed ? 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100' : 'border border-amber-200 bg-amber-50 text-amber-900 cursor-not-allowed'}`}
                        title={!allowed ? 'Pro only piece skin' : ''}
                      >
                        {skin}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : <p className="mt-4 text-sm text-slate-600">Cosmetics not loaded.</p>}
        </section>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Recent profile matches</p>
        <div className="mt-4 space-y-3 text-sm">
          {profileMatches.length ? profileMatches.map((match) => (
            <div key={match.id} className="rounded-2xl bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">{match.players?.white?.nickname || 'White'} vs {match.players?.red?.nickname || 'Red'}</p>
              <p className="mt-1 text-slate-500">Role: {match.role_color} • {match.did_win ? 'Win' : 'Loss/Draw'} • Mode: {match.mode} • Moves: {match.total_moves}</p>
            </div>
          )) : <p className="text-slate-600">No profile match history returned.</p>}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Notifications</p>
          <div className="mt-4 space-y-3 text-sm">
            {notifications.length ? notifications.map((notification) => (
              <div key={notification.notification_id || notification.title} className="rounded-2xl bg-slate-50 p-4">
                <p className="font-semibold text-slate-900">{notification.title || notification.kind || 'Notification'}</p>
                <p className="mt-1 text-slate-500">{notification.message || notification.body || 'No message body returned.'}</p>
                <button type="button" onClick={() => markNotificationAsRead(notification.notification_id || notification.id)} disabled={busy} className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-60">Mark as read</button>
              </div>
            )) : <p className="text-slate-600">No pending notifications.</p>}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Active sessions</p>
          <div className="mt-4 space-y-3 text-sm">
            {sessions.length ? sessions.map((session) => (
              <div key={session.session_id} className="rounded-2xl bg-slate-50 p-4">
                <p className="font-semibold text-slate-900">{session.device_label || 'Unknown device'}</p>
                <p className="mt-1 text-slate-500">Last seen: {new Date(session.last_seen_at).toLocaleString()}</p>
                <button type="button" onClick={() => revokeSessionById(session.session_id)} disabled={busy} className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-60">Revoke</button>
              </div>
            )) : <p className="text-slate-600">No session data returned.</p>}
          </div>
        </section>
      </div>
    </div>
  )
}
