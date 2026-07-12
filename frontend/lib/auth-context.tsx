"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/endpoints";
import { getToken, onUnauthorized, setToken } from "@/lib/api/client";
import type { UserOut } from "@/lib/api/types";

interface LoginResult {
  mfaRequired: boolean;
  pendingToken?: string;
}

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<LoginResult>;
  verifyMfa: (pendingToken: string, code: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    const me = await authApi.me();
    setUser(me);
  }, []);

  useEffect(() => {
    onUnauthorized(() => {
      setToken(null);
      setUser(null);
      router.replace("/login");
    });
  }, [router]);

  useEffect(() => {
    (async () => {
      try {
        await refreshUser();
      } catch {
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
    // Only run once on mount - refreshUser is stable across renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<LoginResult> => {
    const response = await authApi.login(username, password);
    if (response.mfa_required) {
      return { mfaRequired: true, pendingToken: response.pending_token ?? undefined };
    }
    setToken(response.access_token);
    const me = await authApi.me();
    setUser(me);
    return { mfaRequired: false };
  }, []);

  const verifyMfa = useCallback(async (pendingToken: string, code: string) => {
    const response = await authApi.verifyMfa(pendingToken, code);
    setToken(response.access_token);
    const me = await authApi.me();
    setUser(me);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, verifyMfa, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function hasRole(user: UserOut | null, minimum: "viewer" | "reviewer" | "editor" | "admin") {
  if (!user) return false;
  const rank: Record<string, number> = { viewer: 0, reviewer: 1, editor: 2, admin: 3 };
  return rank[user.role] >= rank[minimum];
}
