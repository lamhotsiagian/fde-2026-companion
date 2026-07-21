'use client';

import { useAuth } from '@/lib/auth';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/api';
import { Thread } from '@/lib/types';
import {
  BrainCircuit, MessageSquare, Database, LogOut, Plus, Trash2, Menu, X, Sparkles,
} from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const [threads, setThreads] = useState<Thread[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const loadThreads = async () => {
    try {
      const res = await fetchWithAuth('/threads/');
      if (res.ok) setThreads(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (user) loadThreads();
  }, [user]);

  // Close the mobile drawer on navigation
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  const createThread = async () => {
    try {
      const res = await fetchWithAuth('/threads/', { method: 'POST' });
      if (res.ok) {
        const newThread = await res.json();
        setThreads((prev) => [newThread, ...prev]);
        router.push(`/chat/${newThread.id}`);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const deleteThread = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm('Delete this conversation? Its stored messages will be removed.')) return;
    try {
      const res = await fetchWithAuth(`/threads/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setThreads((prev) => prev.filter((t) => t.id !== id));
        if (pathname.includes(id)) router.push('/chat');
      }
    } catch (e) {
      console.error(e);
    }
  };

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 p-8 card">
          <BrainCircuit className="w-10 h-10 text-[var(--accent)] animate-pulse" />
          <span className="text-sm font-medium text-[var(--muted)]">Loading your workspace…</span>
        </div>
      </div>
    );
  }

  const navLink = (active: boolean) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
      active
        ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]'
        : 'text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]'
    }`;

  const sidebar = (
    <aside className="w-72 bg-[var(--surface)] border-r border-[var(--border)] flex flex-col h-full shrink-0">
      {/* Logo */}
      <div className="h-16 px-5 flex items-center justify-between border-b border-[var(--border)]">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="p-1.5 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-lg">
            <BrainCircuit className="w-5 h-5 text-[var(--accent)]" />
          </div>
          <span className="font-bold text-base tracking-tight">FDE System RAG</span>
        </Link>
        <button onClick={() => setSidebarOpen(false)} className="lg:hidden btn btn-ghost p-1.5">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* New chat */}
      <div className="p-3">
        <button onClick={createThread} className="btn btn-primary w-full py-2.5 text-sm">
          <Plus className="w-4 h-4" /> New chat
        </button>
      </div>

      {/* Threads */}
      <div className="flex-1 overflow-y-auto px-3 pb-2 flex flex-col gap-0.5">
        <div className="text-xs uppercase tracking-wider text-[var(--subtle)] font-semibold px-2 py-2">
          Conversations
        </div>
        {threads.map((t) => {
          const isActive = pathname.includes(t.id);
          return (
            <Link
              key={t.id}
              href={`/chat/${t.id}`}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg text-sm transition ${
                isActive
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-text)] font-medium'
                  : 'text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]'
              }`}
            >
              <div className="flex items-center gap-2.5 overflow-hidden mr-2">
                <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? 'text-[var(--accent)]' : 'text-[var(--subtle)]'}`} />
                <span className="truncate">{t.title}</span>
              </div>
              <button
                onClick={(e) => deleteThread(t.id, e)}
                className="opacity-0 group-hover:opacity-100 text-[var(--subtle)] hover:text-[var(--danger)] p-1 rounded-md transition hover:bg-[var(--danger-soft)] shrink-0"
                aria-label="Delete conversation"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </Link>
          );
        })}
        {threads.length === 0 && (
          <div className="text-center text-[var(--subtle)] py-8 text-sm">No conversations yet.</div>
        )}
      </div>

      {/* Bottom nav + user */}
      <div className="p-3 border-t border-[var(--border)] flex flex-col gap-1">
        <div className="flex items-center justify-between pt-1">
          <div className="flex flex-col overflow-hidden">
            <span className="text-sm font-semibold truncate">{user.username}</span>
            <span className="text-xs text-[var(--subtle)] truncate">{user.email}</span>
          </div>
          <button onClick={logout} className="btn btn-ghost p-2" title="Sign out" aria-label="Sign out">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex">{sidebar}</div>

      {/* Mobile drawer */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
          <div className="relative z-50 animate-fade-in">{sidebar}</div>
        </div>
      )}

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile top bar */}
        <div className="lg:hidden h-14 px-4 flex items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] shrink-0">
          <button onClick={() => setSidebarOpen(true)} className="btn btn-ghost p-2" aria-label="Open menu">
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-semibold">Memory RAG</span>
        </div>
        <div className="flex-1 flex flex-col overflow-hidden">{children}</div>
      </main>
    </div>
  );
}
