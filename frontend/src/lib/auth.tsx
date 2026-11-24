// Who is logged in? Shared with every staff page through React "context".
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean; // true while we check a saved token on first load
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => Boolean(getToken()));

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  // On first load: if a token was saved earlier, find out who it belongs to.
  useEffect(() => {
    setUnauthorizedHandler(logout); // an expired token anywhere logs out
    if (!getToken()) return;
    api.me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    setToken(result.token);
    setUser(result.user);
    return result.user;
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside <AuthProvider>");
  return state;
}

export const isAdmin = (user: User | null) => user?.role === "admin";
