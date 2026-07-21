'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { BACKEND_URL } from '@/lib/api';
import { BrainCircuit, AlertCircle, Loader, Users } from 'lucide-react';

// Seeded demo accounts (see backend/app/db/seed.py). Shared password.
const DEMO_ACCOUNTS = [
  { email: 'alice@example.com', role: 'Backend engineer' },
  { email: 'bob@example.com', role: 'Data scientist' },
  { email: 'carol@example.com', role: 'Product manager' },
  { email: 'dave@example.com', role: 'DevOps engineer' },
];
const DEMO_PASSWORD = 'Password123!';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          username: email, // FastAPI OAuth2PasswordRequestForm expects 'username'
          password: password,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        login(data.access_token, data.refresh_token, data.user);
      } else {
        setError(data.detail || 'Login failed. Please check your credentials.');
      }
    } catch {
      setError('Could not reach the server. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md card p-8 flex flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="p-2.5 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-xl">
            <BrainCircuit className="text-[var(--accent)] w-7 h-7" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Welcome back</h1>
            <p className="text-[var(--muted)] text-sm mt-1">Sign in to your Memory RAG workspace</p>
          </div>
        </div>

        {error && (
          <div className="bg-[var(--danger-soft)] border border-[var(--danger-border)] text-[var(--danger)] p-3 rounded-xl flex items-start gap-2 text-sm">
            <AlertCircle className="w-5 h-5 shrink-0 mt-px" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="field-label">Email or username</label>
            <input
              type="text"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="input"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="field-label">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="input"
            />
          </div>

          <button type="submit" disabled={loading} className="btn btn-primary py-2.5 mt-1">
            {loading ? <Loader className="w-5 h-5 animate-spin" /> : 'Sign in'}
          </button>
        </form>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3.5 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--muted)]">
            <Users className="w-4 h-4" /> Demo accounts — click to fill (password {DEMO_PASSWORD})
          </div>
          <div className="grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.email}
                type="button"
                onClick={() => { setEmail(a.email); setPassword(DEMO_PASSWORD); }}
                className="text-left rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 hover:border-[var(--accent)] transition"
              >
                <span className="block text-xs font-medium text-[var(--foreground)] truncate">{a.email}</span>
                <span className="block text-[11px] text-[var(--subtle)]">{a.role}</span>
              </button>
            ))}
          </div>
        </div>

        <p className="text-center text-sm text-[var(--muted)]">
          New here?{' '}
          <Link href="/signup" className="text-[var(--accent)] font-semibold hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
