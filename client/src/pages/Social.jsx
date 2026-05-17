import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

export default function Social({ auth }) {
  const [friends, setFriends] = useState([])
  const [pendingRequests, setPendingRequests] = useState([])
  const [mutedProfileIds, setMutedProfileIds] = useState([])
  const [targetProfileId, setTargetProfileId] = useState('')
  const [muteProfileId, setMuteProfileId] = useState('')
  const [error, setError] = useState('')
  const [actionMessage, setActionMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [sessionToken, setSessionToken] = useState(auth.token || '')

  useEffect(() => {
    setSessionToken(auth.token || '')
  }, [auth.token])

  const formatApiError = (value) => {
    if (!value) {
      return 'Unknown error'
    }

    if (typeof value === 'string') {
      return value
    }

    if (Array.isArray(value)) {
      return value.map((item) => formatApiError(item)).filter(Boolean).join(', ')
    }

    if (typeof value === 'object') {
      if (typeof value.msg === 'string') {
        return value.msg
      }
      if (typeof value.detail === 'string') {
        return value.detail
      }
      if (Array.isArray(value.detail)) {
        return formatApiError(value.detail)
      }
    }

    return String(value)
  }

  const refreshSession = async () => {
    if (!auth.refreshToken) {
      throw new Error('Session expired. Please sign in again.')
    }

    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: auth.refreshToken }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`)
    }

    window.localStorage.setItem('checkers.token', data.access_token)
    window.localStorage.setItem('checkers.refresh_token', data.refresh_token)
    window.localStorage.setItem('checkers.session_id', data.session_id)
    setSessionToken(data.access_token)
    return data.access_token
  }

  useEffect(() => {
    let isMounted = true

    async function load() {
      if (!auth.token) {
        setFriends([])
        setPendingRequests([])
        setMutedProfileIds([])
        return
      }

      try {
        const [friendsResponse, muteResponse] = await Promise.all([
          fetch(`${API_BASE}/social/friends`, {
          headers: { Authorization: `Bearer ${sessionToken}` },
          }),
          fetch(`${API_BASE}/social/chat/mute`, {
            headers: { Authorization: `Bearer ${sessionToken}` },
          }),
        ])
        const friendsData = await friendsResponse.json().catch(() => ({}))
        const muteData = await muteResponse.json().catch(() => ({}))
        if (!friendsResponse.ok) {
          setError(friendsData.detail || 'Could not load social graph.')
          return
        }

        if (isMounted) {
          setFriends(friendsData.friends || [])
          setPendingRequests(friendsData.pending_requests || [])
          setMutedProfileIds(muteData.muted_profile_ids || [])
        }
      } catch {
        if (isMounted) {
          setError('Could not load social graph.')
        }
      }
    }

    load()
    return () => {
      isMounted = false
    }
  }, [sessionToken])

  const apiCall = async (path, options = {}, retrying = false, tokenOverride = null) => {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${tokenOverride || sessionToken}`,
      },
    })
    const data = await response.json().catch(() => ({}))

    if (response.status === 401 && !retrying) {
      try {
        const nextToken = await refreshSession()
        return await apiCall(path, options, true, nextToken)
      } catch (refreshError) {
        throw new Error(formatApiError(refreshError?.message || data.detail || `HTTP ${response.status}`))
      }
    }

    if (!response.ok) {
      throw new Error(formatApiError(data.detail || `HTTP ${response.status}`))
    }
    return data
  }

  const sendFriendRequest = async () => {
    const target = targetProfileId.trim()
    if (!target) {
      return
    }

    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall('/social/friends/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_profile_id: target }),
      })
      setActionMessage(data.message || 'Friend request sent')
      setTargetProfileId('')
      await Promise.all([loadFriends(), loadMutes()])
    } catch (error) {
      setActionMessage(`Could not send request (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const loadFriends = async () => {
    const data = await apiCall('/social/friends')
    setFriends(data.friends || [])
    setPendingRequests(data.pending_requests || [])
  }

  const loadMutes = async () => {
    const data = await apiCall('/social/chat/mute')
    setMutedProfileIds(data.muted_profile_ids || [])
  }

  const acceptFriendRequest = async (friendshipId) => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall('/social/friends/accept', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ friendship_id: friendshipId }),
      })
      setActionMessage(data.message || 'Friend request accepted')
      await loadFriends()
    } catch (error) {
      setActionMessage(`Could not accept request (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const removeFriend = async (targetId) => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall(`/social/friends/${encodeURIComponent(targetId)}`, { method: 'DELETE' })
      setActionMessage(data.message || 'Friend removed')
      await loadFriends()
    } catch (error) {
      setActionMessage(`Could not remove friend (${error.message})`)
    } finally {
      setBusy(false)
    }
  }

  const updateMute = async (muteId, muted) => {
    setBusy(true)
    setActionMessage('')
    try {
      const data = await apiCall('/social/chat/mute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ muted_profile_id: muteId, muted }),
      })
      setActionMessage(data.message || 'Mute preferences updated')
      setMuteProfileId('')
      await loadMutes()
    } catch (error) {
      setActionMessage(`Could not update mute (${formatApiError(error?.message || error)})`)
    } finally {
      setBusy(false)
    }
  }

  if (!auth.isAuthenticated) {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Social</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Friends, requests, and chat controls</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">Sign in to load your friends list, pending requests, mute settings, and chat-adjacent social controls.</p>
        <button type="button" onClick={auth.openAuth} className="mt-6 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-700">
          Sign in to open social
        </button>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-gradient-to-br from-rose-100 via-white to-orange-50 p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-700">Social</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">Your social layer is now on its own page</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">This screen now reads the existing friends and request APIs instead of showing a placeholder sentence.</p>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Your profile id</p>
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <span className="font-mono text-xs break-all">{auth.profileId || 'No profile id available'}</span>
          {auth.profileId ? (
            <button
              type="button"
              onClick={() => navigator.clipboard?.writeText(auth.profileId)}
              className="ml-auto rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              Copy
            </button>
          ) : null}
        </div>
        <p className="mt-3 text-sm text-slate-600">Use another player’s profile id in the friend request field below.</p>
      </section>

      {error ? <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p> : null}
      {actionMessage ? <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">{actionMessage}</p> : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Friend actions</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <input value={targetProfileId} onChange={(event) => setTargetProfileId(event.target.value)} placeholder="Target profile id" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm" />
          <button type="button" onClick={sendFriendRequest} disabled={busy} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">Send request</button>
          <input value={muteProfileId} onChange={(event) => setMuteProfileId(event.target.value)} placeholder="Mute profile id" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm" />
          <button type="button" onClick={() => updateMute(muteProfileId.trim(), true)} disabled={busy || !muteProfileId.trim()} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Mute</button>
          <button type="button" onClick={() => updateMute(muteProfileId.trim(), false)} disabled={busy || !muteProfileId.trim()} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">Unmute</button>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Friends</p>
          <div className="mt-4 space-y-3">
            {friends.length ? friends.map((friend) => (
              <div key={friend.friendship_id} className="rounded-2xl bg-slate-50 p-4 text-sm">
                <p className="font-semibold text-slate-900">{friend.nickname}</p>
                <p className="mt-1 text-slate-500">{friend.city || 'No city'} • {friend.status}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => removeFriend(friend.profile_id)} disabled={busy} className="rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-60">Remove</button>
                  <button type="button" onClick={() => updateMute(friend.profile_id, !mutedProfileIds.includes(friend.profile_id))} disabled={busy} className="rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-60">{mutedProfileIds.includes(friend.profile_id) ? 'Unmute' : 'Mute'}</button>
                </div>
              </div>
            )) : <p className="text-sm text-slate-600">No friends loaded for this account yet.</p>}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Pending requests</p>
          <div className="mt-4 space-y-3">
            {pendingRequests.length ? pendingRequests.map((request) => (
              <div key={request.friendship_id} className="rounded-2xl bg-slate-50 p-4 text-sm">
                <p className="font-semibold text-slate-900">{request.requester_nickname}</p>
                <p className="mt-1 text-slate-500">{request.requester_city || 'No city'} • waiting for response</p>
                <button type="button" onClick={() => acceptFriendRequest(request.friendship_id)} disabled={busy} className="mt-3 rounded-lg bg-teal-600 px-3 py-1 text-xs font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60">Accept</button>
              </div>
            )) : <p className="text-sm text-slate-600">No pending requests right now.</p>}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Muted profiles</p>
          <div className="mt-4 space-y-3 text-sm">
            {mutedProfileIds.length ? mutedProfileIds.map((profile) => (
              <div key={profile} className="rounded-2xl bg-slate-50 p-4">
                <p className="font-semibold text-slate-900">{profile}</p>
                <button type="button" onClick={() => updateMute(profile, false)} disabled={busy} className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-60">Unmute</button>
              </div>
            )) : <p className="text-slate-600">No muted profiles.</p>}
          </div>
        </section>
      </div>
    </div>
  )
}
