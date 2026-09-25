/**
 * src/context/AuthContext.jsx
 * Global auth state: current user, login/register/logout, and role helpers.
 * Wraps the whole app in main.jsx / App.jsx.
 */

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authAPI, tokenStore } from "../services/api";
import { userSocket } from "../services/socket";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!tokenStore.getAccess()) {
      setLoading(false);
      return;
    }
    try {
      const me = await authAPI.me();
      setUser(me);
      userSocket.connect();
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
    return () => userSocket.disconnect();
  }, [loadMe]);

  const login = async (email, password) => {
    const data = await authAPI.login({ email, password });
    tokenStore.set(data.access, data.refresh);
    setUser(data.user);
    userSocket.connect();
    return data.user;
  };

  const register = async (payload) => {
    const data = await authAPI.register(payload);
    tokenStore.set(data.access, data.refresh);
    setUser(data.user);
    userSocket.connect();
    return data.user;
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch {
      /* ignore network errors on logout */
    }
    tokenStore.clear();
    userSocket.disconnect();
    setUser(null);
  };

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    isRider: user?.role === "RIDER",
    isDriver: user?.role === "DRIVER",
    login,
    register,
    logout,
    refreshUser: loadMe,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
