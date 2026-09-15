const TOKEN_KEY = "nexova_access_token";

// M15: localStorage access was unguarded. Safari private mode, blocked
// site data, or a full storage quota all make these throw
// (SecurityError / QuotaExceededError) rather than fail gracefully --
// previously that meant setToken() throwing right after a *successful*
// login, so the user would see a raw storage error instead of landing
// in the app. Degrading to an in-memory fallback keeps the session
// working for the current page load even when persistent storage isn't
// available; it just won't survive a refresh in that specific case,
// which is an acceptable trade-off against the login flow crashing.
let inMemoryToken: string | null = null;

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return inMemoryToken;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    inMemoryToken = token;
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore -- if storage was inaccessible on write, it's inaccessible
    // on remove too; nothing further to clean up there
  }
  inMemoryToken = null;
}

/**
 * Decodes a JWT's payload without verifying the signature -- this is
 * only ever used client-side to check expiry for UX purposes (e.g.
 * skip a doomed API call). The server is the only party that verifies
 * the signature; this check is not a security boundary.
 */
export function isTokenExpired(token: string): boolean {
  try {
    const payloadBase64 = token.split(".")[1];
    const payload = JSON.parse(atob(payloadBase64));
    if (typeof payload.exp !== "number") return true;
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}

export function hasValidToken(): boolean {
  const token = getToken();
  if (!token) return false;
  return !isTokenExpired(token);
}

export function logout(): void {
  clearToken();
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/login";
}
