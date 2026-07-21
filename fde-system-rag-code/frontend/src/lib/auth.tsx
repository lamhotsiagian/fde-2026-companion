'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { User } from '@/lib/types';
import { fetchWithAuth } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (token: string, refresh: string, userData: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const login = useCallback(
    (token: string, refresh: string, userData: User) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('refresh_token', refresh);
      setUser(userData);
      router.push('/chat');
    },
    [router]
  );

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    router.push('/login');
  }, [router]);

  useEffect(() => {
    async function loadCurrentUser() {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const res = await fetchWithAuth('/users/me');
          if (res.ok) {
            const data = await res.json();
            setUser(data);
          } else {
            logout();
          }
        } catch {
          logout();
        }
      }
      setLoading(false);
    }
    loadCurrentUser();
  }, [logout]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
