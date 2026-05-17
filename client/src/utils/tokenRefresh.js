const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

/**
 * Refresh the access token using the refresh token
 * @param {string} refreshToken - The refresh token stored in localStorage
 * @returns {Promise<{access_token: string, refresh_token: string} | null>} - New tokens or null if refresh fails
 */
export async function refreshAccessToken(refreshToken) {
  if (!refreshToken) {
    return null
  }

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      console.error('Token refresh failed:', response.status)
      return null
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Token refresh error:', error)
    return null
  }
}

/**
 * Fetch wrapper that automatically handles token refresh on 401
 * @param {string} url - The URL to fetch
 * @param {object} options - Fetch options (method, headers, body, etc.)
 * @param {string} currentToken - Current access token
 * @param {string} refreshToken - Refresh token for getting new access token
 * @param {function} onTokenRefreshed - Callback when token is refreshed (receives new token)
 * @returns {Promise<Response>} - The fetch response
 */
export async function fetchWithTokenRefresh(
  url,
  options = {},
  currentToken,
  refreshToken,
  onTokenRefreshed
) {
  // First attempt with current token
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${currentToken}`,
    },
  })

  // If 401, try to refresh token and retry
  if (response.status === 401 && refreshToken) {
    const newTokens = await refreshAccessToken(refreshToken)

    if (newTokens?.access_token) {
      // Notify caller of refreshed token
      if (onTokenRefreshed) {
        onTokenRefreshed(newTokens.access_token, newTokens.refresh_token)
      }

      // Retry request with new token
      response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${newTokens.access_token}`,
        },
      })
    }
  }

  return response
}
