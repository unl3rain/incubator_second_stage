import { useEffect, useState } from 'react'
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom'
import MainNav from './components/navigation/MainNav'
import Home from './pages/Home'
import PlayBoard from './pages/PlayBoard'
import Profile from './pages/Profile'
import Puzzles from './pages/Puzzles'
import Replays from './pages/Replays'
import Social from './pages/Social'
import Stats from './pages/Stats'
import Training from './pages/Training'
import PositionEditor from './pages/PositionEditor'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
const API_ORIGIN = new URL(API_BASE).origin

function App() {
  const [token, setToken] = useState(() => window.localStorage.getItem('checkers.token'))
  const [refreshToken, setRefreshToken] = useState(() => window.localStorage.getItem('checkers.refresh_token'))
  const [profileId, setProfileId] = useState(() => window.localStorage.getItem('checkers.profile_id'))
  const [username, setUsername] = useState(() => window.localStorage.getItem('checkers.username') || 'Player')
  const [darkMode, setDarkMode] = useState(() => window.localStorage.getItem('checkers.darkMode') === 'true')
  const [subscription, setSubscription] = useState(() => window.localStorage.getItem('checkers.subscription') || 'free')
  const [showDemoPayment, setShowDemoPayment] = useState(false)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authUsername, setAuthUsername] = useState('')
  const [authVerificationCode, setAuthVerificationCode] = useState('')
  const [authResetCode, setAuthResetCode] = useState('')
  const [authNewPassword, setAuthNewPassword] = useState('')
  const [authMessage, setAuthMessage] = useState('')
  const [authBusy, setAuthBusy] = useState(false)
  // Demo: upgrade to pro
  const upgradeToPro = () => {
    setSubscription('pro')
    window.localStorage.setItem('checkers.subscription', 'pro')
    setShowDemoPayment(false)
  }

  const persistOAuthAuth = (payload) => {
    persistAuth(payload)
    resetAuthFields()
    setShowAuthModal(false)
    setAuthMode('login')
    setAuthBusy(false)
  }

  useEffect(() => {
    document.body.classList.toggle('theme-dark', darkMode)
    document.body.classList.toggle('theme-light', !darkMode)
    window.localStorage.setItem('checkers.darkMode', String(darkMode))
  }, [darkMode])

  useEffect(() => {
    const handleOauthMessage = (event) => {
      if (event.origin !== API_ORIGIN) {
        return
      }

      const { data } = event
      if (!data || typeof data !== 'object') {
        return
      }

      if (data.type === 'checkers_google_auth_success' || data.type === 'checkers_github_auth_success') {
        persistOAuthAuth(data.payload || {})
        return
      }

      if (data.type === 'checkers_google_auth_error' || data.type === 'checkers_github_auth_error') {
        setAuthMessage(data.payload?.message || 'Social sign-in failed.')
        setAuthBusy(false)
      }
    }

    window.addEventListener('message', handleOauthMessage)
    return () => window.removeEventListener('message', handleOauthMessage)
  }, [])

  useEffect(() => {
    const handleStorageChange = (event) => {
      // Handle token refresh from other parts of the app (e.g., PlayBoard)
      if (event.key === 'checkers.token' && event.newValue && event.newValue !== token) {
        setToken(event.newValue)
      }
      if (event.key === 'checkers.refresh_token' && event.newValue && event.newValue !== refreshToken) {
        setRefreshToken(event.newValue)
      }
      if (event.key === 'checkers.subscription' && event.newValue && event.newValue !== subscription) {
        setSubscription(event.newValue)
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [token, refreshToken, subscription])

  useEffect(() => {
    if (subscription === 'free') {
      let updated = false
      const boardSkin = window.localStorage.getItem('checkers.board_skin')
      const pieceSkin = window.localStorage.getItem('checkers.piece_skin')
      if (boardSkin && boardSkin !== 'classic') {
        window.localStorage.setItem('checkers.board_skin', 'classic')
        updated = true
      }
      if (pieceSkin && pieceSkin !== 'marble') {
        window.localStorage.setItem('checkers.piece_skin', 'marble')
        updated = true
      }
      if (updated) {
        window.dispatchEvent(new Event('checkers-skins-updated'))
      }
    }
  }, [subscription])

  const resetAuthFields = () => {
    setAuthPassword('')
    setAuthVerificationCode('')
    setAuthResetCode('')
    setAuthNewPassword('')
    setAuthMessage('')
  }

  const switchAuthMode = (nextMode) => {
    setAuthMode(nextMode)
    resetAuthFields()
  }

  const persistAuth = (data) => {
    const subscriptionValue = data.subscription || 'free'
    window.localStorage.setItem('checkers.token', data.access_token)
    window.localStorage.setItem('checkers.refresh_token', data.refresh_token)
    window.localStorage.setItem('checkers.session_id', data.session_id)
    window.localStorage.setItem('checkers.profile_id', data.profile_id)
    window.localStorage.setItem('checkers.username', data.username)
    window.localStorage.setItem('checkers.subscription', subscriptionValue)
    setToken(data.access_token)
    setRefreshToken(data.refresh_token)
    setProfileId(data.profile_id)
    setUsername(data.username)
    setSubscription(subscriptionValue)
  }

  const readResponse = async (response) => {
    const text = await response.text()
    if (!text) {
      return {}
    }

    try {
      return JSON.parse(text)
    } catch {
      return { detail: `Request failed (HTTP ${response.status})` }
    }
  }

  const openSocialLogin = async (provider) => {
    setAuthBusy(true)
    setAuthMessage('')

    try {
      const oauthSession = window.crypto?.randomUUID ? window.crypto.randomUUID() : `oauth-${Date.now()}-${Math.random().toString(16).slice(2)}`
      const response = await fetch(`${API_BASE}/auth/${provider}/start?oauth_session=${encodeURIComponent(oauthSession)}`)
      const data = await readResponse(response)

      if (!response.ok) {
        setAuthMessage(data.detail || `${provider === 'google' ? 'Google' : 'GitHub'} sign-in could not start.`)
        return
      }

      const popup = window.open(data.auth_url, `${provider}-oauth`, 'width=520,height=700')
      if (!popup) {
        setAuthMessage('Popup blocked. Allow popups to continue with social sign-in.')
        return
      }

      popup.focus()
    } catch {
      setAuthMessage('Social sign-in request failed. Check that the backend is running.')
    } finally {
      setAuthBusy(false)
    }
  }

  const handleAuthAction = async () => {
    setAuthBusy(true)
    setAuthMessage('')

    try {
      if (authMode === 'register') {
        const response = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: authEmail.trim(),
            password: authPassword,
            username: authUsername.trim() || null,
          }),
        })
        const data = await readResponse(response)
        if (!response.ok) {
          setAuthMessage(data.detail || 'Registration failed.')
          return
        }

        setAuthMessage('Registered. Check your email for the verification code.')
        setAuthMode('verify')
        return
      }

      if (authMode === 'verify') {
        const response = await fetch(`${API_BASE}/auth/verify-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: authEmail.trim(),
            code: authVerificationCode.trim(),
          }),
        })
        const data = await readResponse(response)
        if (!response.ok) {
          setAuthMessage(data.detail || 'Verification failed.')
          return
        }

        setAuthMessage(data.message || 'Email verified. You can log in now.')
        setAuthMode('login')
        return
      }

      if (authMode === 'forgot') {
        const response = await fetch(`${API_BASE}/auth/forgot-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: authEmail.trim() }),
        })
        const data = await readResponse(response)
        if (!response.ok) {
          setAuthMessage(data.detail || 'Could not start password reset.')
          return
        }

        setAuthMessage(data.message || 'Reset code sent.')
        setAuthMode('reset')
        return
      }

      if (authMode === 'reset') {
        const response = await fetch(`${API_BASE}/auth/reset-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: authEmail.trim(),
            code: authResetCode.trim(),
            new_password: authNewPassword,
          }),
        })
        const data = await readResponse(response)
        if (!response.ok) {
          setAuthMessage(data.detail || 'Password reset failed.')
          return
        }

        setAuthMessage(data.message || 'Password reset complete. Log in with your new password.')
        setAuthMode('login')
        return
      }

      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: authEmail.trim() || null,
          username: authUsername.trim() || null,
          password: authPassword || null,
        }),
      })
      const data = await readResponse(response)
      if (!response.ok) {
        setAuthMessage(data.detail || 'Login failed.')
        return
      }

      persistAuth(data)
      resetAuthFields()
      setShowAuthModal(false)
      setAuthMode('login')
    } catch {
      setAuthMessage('Authentication request failed. Check that the backend is running.')
    } finally {
      setAuthBusy(false)
    }
  }

  const handleLogout = async () => {
    try {
      if (token) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
      }
    } catch {
      // Clear local state even if the backend logout call fails.
    }

    window.localStorage.removeItem('checkers.token')
    window.localStorage.removeItem('checkers.refresh_token')
    window.localStorage.removeItem('checkers.session_id')
    window.localStorage.removeItem('checkers.profile_id')
    window.localStorage.removeItem('checkers.username')
    setToken(null)
    setRefreshToken(null)
    setProfileId(null)
    setUsername('Player')
    setSubscription('free')
    window.localStorage.setItem('checkers.subscription', 'free')
  }

  const auth = {
    token,
    refreshToken,
    profileId,
    username,
    isAuthenticated: Boolean(token),
    subscription,
    openAuth: () => {
      switchAuthMode('login')
      setShowAuthModal(true)
    },
    openDemoPayment: () => setShowDemoPayment(true),
  }

  const openLoginModal = () => {
    switchAuthMode('login')
    setShowAuthModal(true)
  }

  return (
    <Router>
      <div className="app-main min-h-screen">
        <MainNav
          isAuthenticated={auth.isAuthenticated}
          username={username}
          subscription={subscription}
          darkMode={darkMode}
          onToggleTheme={() => setDarkMode((current) => !current)}
          onLogin={openLoginModal}
          onLogout={handleLogout}
          onUpgrade={() => setShowDemoPayment(true)}
        />

        <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-8">
          <Routes>
            <Route path="/" element={<Home auth={auth} />} />
            <Route path="/training" element={<Training auth={auth} />} />
            <Route path="/position-editor" element={<PositionEditor auth={auth} />} />
            <Route path="/puzzles" element={<Puzzles auth={auth} />} />
            <Route path="/replays" element={<Replays auth={auth} />} />
            <Route path="/stats" element={<Stats auth={auth} />} />
            <Route path="/social" element={<Social auth={auth} />} />
            <Route path="/profile" element={<Profile auth={auth} />} />
            <Route path="/play" element={auth.isAuthenticated ? <PlayBoard auth={auth} /> : <Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>

          {showDemoPayment ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 px-4">
              <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
                <h2 className="text-2xl font-bold text-slate-900 mb-4">Upgrade to Pro</h2>
                <p className="mb-4 text-slate-700">Unlock all training features and premium board skins!</p>
                <button
                  type="button"
                  className="w-full rounded-xl bg-emerald-600 px-4 py-3 text-lg font-semibold text-white transition hover:bg-emerald-700 mb-2"
                  onClick={upgradeToPro}
                >
                  Demo Payment (Unlock Pro)
                </button>
                <button
                  type="button"
                  className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg font-semibold text-slate-700 transition hover:bg-slate-50"
                  onClick={() => setShowDemoPayment(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
        </main>

        {showAuthModal ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 px-4">
            <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Account</p>
                  <h2 className="mt-2 text-2xl font-bold text-slate-900">
                    {authMode === 'register' ? 'Create account' : authMode === 'verify' ? 'Verify email' : authMode === 'forgot' ? 'Reset password' : authMode === 'reset' ? 'Choose new password' : 'Sign in'}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAuthModal(false)}
                  className="rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:bg-slate-50"
                >
                  Close
                </button>
              </div>

              <div className="mt-6 space-y-4">
                {authMode === 'login' ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => openSocialLogin('google')}
                      disabled={authBusy}
                      className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Continue with Google
                    </button>
                    <button
                      type="button"
                      onClick={() => openSocialLogin('github')}
                      disabled={authBusy}
                      className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Continue with GitHub
                    </button>
                  </div>
                ) : null}

                {(authMode === 'register' || authMode === 'login') ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Username
                    <input
                      value={authUsername}
                      onChange={(event) => setAuthUsername(event.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                      placeholder="GuestMaster"
                    />
                  </label>
                ) : null}

                <label className="block text-sm font-medium text-slate-700">
                  Email
                  <input
                    type="email"
                    value={authEmail}
                    onChange={(event) => setAuthEmail(event.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    placeholder="you@example.com"
                  />
                </label>

                {(authMode === 'login' || authMode === 'register') ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Password
                    <input
                      type="password"
                      value={authPassword}
                      onChange={(event) => setAuthPassword(event.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                      placeholder="••••••••"
                    />
                  </label>
                ) : null}

                {authMode === 'verify' ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Verification code
                    <input
                      value={authVerificationCode}
                      onChange={(event) => setAuthVerificationCode(event.target.value)}
                      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    />
                  </label>
                ) : null}

                {authMode === 'reset' ? (
                  <>
                    <label className="block text-sm font-medium text-slate-700">
                      Reset code
                      <input
                        value={authResetCode}
                        onChange={(event) => setAuthResetCode(event.target.value)}
                        className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                      />
                    </label>
                    <label className="block text-sm font-medium text-slate-700">
                      New password
                      <input
                        type="password"
                        value={authNewPassword}
                        onChange={(event) => setAuthNewPassword(event.target.value)}
                        className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                      />
                    </label>
                  </>
                ) : null}
              </div>

              {authMessage ? <p className="mt-4 text-sm text-slate-600">{authMessage}</p> : null}

              <button
                type="button"
                onClick={handleAuthAction}
                disabled={authBusy}
                className="mt-6 w-full rounded-xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {authBusy ? 'Working...' : authMode === 'register' ? 'Create account' : authMode === 'verify' ? 'Verify email' : authMode === 'forgot' ? 'Send reset code' : authMode === 'reset' ? 'Set new password' : 'Sign in'}
              </button>

              <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-600">
                {authMode !== 'login' ? (
                  <button type="button" onClick={() => switchAuthMode('login')} className="underline underline-offset-4">
                    Sign in
                  </button>
                ) : null}
                {authMode !== 'register' ? (
                  <button type="button" onClick={() => switchAuthMode('register')} className="underline underline-offset-4">
                    Register
                  </button>
                ) : null}
                {authMode !== 'forgot' ? (
                  <button type="button" onClick={() => switchAuthMode('forgot')} className="underline underline-offset-4">
                    Forgot password
                  </button>
                ) : null}
                {authMode !== 'verify' ? (
                  <button type="button" onClick={() => switchAuthMode('verify')} className="underline underline-offset-4">
                    Verify email
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

      </div>
    </Router>
  )
}

export default App
