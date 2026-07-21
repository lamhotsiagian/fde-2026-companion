'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BACKEND_URL } from '@/lib/api';
import { BrainCircuit, AlertCircle, CheckCircle2, Loader } from 'lucide-react';

export default function SignupPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          email,
          password,
          first_name: firstName,
          last_name: lastName,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccess('Account created. Taking you to sign in…');
        setTimeout(() => router.push('/login'), 1500);
      } else {
        setError(data.detail || 'Signup failed. Please try again.');
      }
    } catch {
      setError('Could not reach the server. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-lg card p-8 flex flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="p-2.5 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-xl">
            <BrainCircuit className="text-[var(--accent)] w-7 h-7" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Create your account</h1>
            <p className="text-[var(--muted)] text-sm mt-1">Each account gets its own private memory</p>
          </div>
        </div>

        {error && (
          <div className="bg-[var(--danger-soft)] border border-[var(--danger-border)] text-[var(--danger)] p-3 rounded-xl flex items-start gap-2 text-sm">
            <AlertCircle className="w-5 h-5 shrink-0 mt-px" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="bg-[var(--success-soft)] border border-[var(--success-border)] text-[var(--success)] p-3 rounded-xl flex items-start gap-2 text-sm">
            <CheckCircle2 className="w-5 h-5 shrink-0 mt-px" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <label className="field-label">Username</label>
            <input type="text" required value={username} onChange={(e) => setUsername(e.target.value)} placeholder="janedoe" className="input" />
          </div>

          <div className="flex flex-col gap-1.5 md:col-span-2">
            <label className="field-label">Email</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="input" />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="field-label">First name</label>
            <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="Jane" className="input" />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="field-label">Last name</label>
            <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Doe" className="input" />
          </div>

          <div className="flex flex-col gap-1.5 md:col-span-2">
            <label className="field-label">Password (at least 8 characters)</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="input" />
          </div>

          <button type="submit" disabled={loading} className="btn btn-primary py-2.5 mt-1 md:col-span-2">
            {loading ? <Loader className="w-5 h-5 animate-spin" /> : 'Create account'}
          </button>
        </form>

        <p className="text-center text-sm text-[var(--muted)]">
          Already have an account?{' '}
          <Link href="/login" className="text-[var(--accent)] font-semibold hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
