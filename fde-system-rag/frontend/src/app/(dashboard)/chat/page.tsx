'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchWithAuth } from '@/lib/api';
import { Plus, BrainCircuit, Loader } from 'lucide-react';

export default function ChatIndexPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const startNewChat = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth('/threads/', { method: 'POST' });
      if (res.ok) {
        const thread = await res.json();
        router.push(`/chat/${thread.id}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md flex flex-col items-center gap-6 card p-10">
        <div className="p-4 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-2xl">
          <BrainCircuit className="w-10 h-10 text-[var(--accent)]" />
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="text-lg font-bold">No conversation selected</h2>
          <p className="text-[var(--muted)] text-sm leading-relaxed">
            Pick a conversation from the sidebar, or start a new one. The agent remembers what you tell it across chats.
          </p>
        </div>
        <button onClick={startNewChat} disabled={loading} className="btn btn-primary px-6 py-3 text-sm">
          {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
          {loading ? 'Starting…' : 'New chat'}
        </button>
      </div>
    </div>
  );
}
