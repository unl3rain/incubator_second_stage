import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/training', label: 'Training' },
  { to: '/position-editor', label: 'Position Editor' },
  { to: '/puzzles', label: 'Puzzles' },
  { to: '/replays', label: 'Replays' },
  { to: '/stats', label: 'Stats' },
  { to: '/social', label: 'Social' },
  { to: '/profile', label: 'Profile' },
  { to: '/play', label: 'Play' },
]

export default function MainNav({
  isAuthenticated,
  username,
  subscription,
  darkMode,
  onToggleTheme,
  onLogin,
  onLogout,
  onUpgrade,
}) {
  return (
    <nav className="border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Checkers hub</p>
            {isAuthenticated ? (
              <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${subscription === 'pro' ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}>
                {subscription === 'pro' ? 'Pro member' : 'Free user'}
              </span>
            ) : null}
          </div>
          <p className="text-sm text-slate-500">{isAuthenticated ? `Signed in as ${username}` : 'Guest browsing mode'}</p>
        </div>

        <div className="flex w-full flex-nowrap gap-2 overflow-x-auto pb-1 text-sm lg:w-auto lg:flex-wrap lg:overflow-visible lg:pb-0">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `shrink-0 rounded-full px-4 py-2 transition ${
                  isActive
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`
              }
              end={item.to === '/'}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2 text-xs sm:text-sm">
          {subscription !== 'pro' ? (
            <button
              type="button"
              onClick={onUpgrade}
              className="rounded-lg bg-amber-100 px-3 py-2 font-semibold text-amber-900 transition hover:bg-amber-200"
            >
              Go Pro
            </button>
          ) : null}
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-semibold text-slate-700 transition hover:bg-slate-100"
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            title="Toggle dark mode"
          >
            {darkMode ? 'Light' : 'Dark'}
          </button>

          {!isAuthenticated ? (
            <button
              type="button"
              onClick={onLogin}
              className="rounded-lg bg-teal-600 px-3 py-2 font-semibold text-white transition hover:bg-teal-700"
            >
              Login
            </button>
          ) : (
            <button
              type="button"
              onClick={onLogout}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              Logout
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}
