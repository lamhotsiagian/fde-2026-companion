'use client';

import Link from 'next/link';
import { BrainCircuit, ArrowRight, ShieldCheck, Database, Layers, MessageSquare } from 'lucide-react';

const FEATURES = [
  {
    icon: Database,
    title: 'Layered storage',
    desc: 'Keeps facts in a SQL database, a pgvector index for similarity search, and conversation checkpoints — all working together.',
  },
  {
    icon: BrainCircuit,
    title: 'Reads and writes memory',
    desc: 'Pulls relevant facts into each reply and saves new ones automatically, scored by how important and recent they are.',
  },
  {
    icon: Layers,
    title: 'Consolidation',
    desc: 'Summarizes long conversations into compact memories, spots contradictions, and lets you resolve them.',
  },
  {
    icon: ShieldCheck,
    title: 'Privacy controls',
    desc: 'Export your data anytime, or permanently delete everything the agent remembers about you.',
  },
];

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <header className="w-full border-b border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-lg">
              <BrainCircuit className="text-[var(--accent)] w-5 h-5" />
            </div>
            <span className="font-bold text-lg tracking-tight">Memory RAG</span>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className="btn btn-ghost px-4 py-2 text-sm">Sign in</Link>
            <Link href="/signup" className="btn btn-primary px-4 py-2 text-sm">Get started</Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1 max-w-6xl mx-auto px-6 w-full">
        <section className="py-20 lg:py-28 flex flex-col items-center text-center gap-6">
          <span className="badge bg-[var(--accent-soft)] text-[var(--accent-text)] border-[var(--accent-border)] px-3 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)]" />
            Runs locally with Ollama
          </span>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight max-w-3xl leading-[1.1]">
            A chat agent that actually
            <span className="text-[var(--accent)]"> remembers you</span>
          </h1>
          <p className="text-[var(--muted)] text-lg max-w-2xl leading-relaxed">
            Memory RAG gives a local LLM a real memory system. Chat with it, upload documents, and watch
            exactly what it stores, retrieves, and forgets over time.
          </p>
          <div className="flex flex-wrap gap-3 justify-center mt-2">
            <Link href="/signup" className="btn btn-primary px-6 py-3 text-sm">
              Start chatting <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="/login" className="btn btn-secondary px-6 py-3 text-sm">
              Sign in
            </Link>
          </div>
        </section>

        {/* Features */}
        <section className="pb-24 grid grid-cols-1 sm:grid-cols-2 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="card card-hover p-6 flex flex-col gap-3 text-left">
              <div className="p-2.5 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-xl w-fit">
                <f.icon className="text-[var(--accent)] w-5 h-5" />
              </div>
              <h3 className="font-semibold text-lg">{f.title}</h3>
              <p className="text-[var(--muted)] text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-[var(--subtle)]">
          <span>&copy; 2026 Memory RAG</span>
          <div className="flex items-center gap-5">
            <Link href="/login" className="hover:text-[var(--foreground)] transition flex items-center gap-1.5">
              <MessageSquare className="w-4 h-4" /> Chat
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
