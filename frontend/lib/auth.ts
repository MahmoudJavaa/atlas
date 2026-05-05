/**
 * Auth store — manages JWT token + current user in localStorage.
 * Simple and compatible with the existing axios-based api.ts.
 */

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  plan: string;
}

const TOKEN_KEY = "atlas_token";
const USER_KEY = "atlas_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  // Dispatch custom event so components can react
  window.dispatchEvent(new Event("atlas-auth-change"));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("atlas-auth-change"));
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
