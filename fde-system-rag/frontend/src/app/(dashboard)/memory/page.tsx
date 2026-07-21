'use client';

import { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/api';
import { Memory, MemoryConflict, MemoryStats } from '@/lib/types';
import { Database, Search, Trash2, AlertTriangle, CheckCircle2, Loader } from 'lucide-react';

interface SearchResult {
  memory?: Memory;
  relevance_score: number;
  final_score: number;
}

const TYPE_STYLES: Record<string, string> = {
  episodic: 'bg-[var(--success-soft)] text-[var(--success)] border-[var(--success-border)]',
  semantic: 'bg-[var(--accent-soft)] text-[var(--accent-text)] border-[var(--accent-border)]',
  procedural: 'bg-violet-50 text-violet-700 border-violet-200',
  entity: 'bg-amber-50 text-amber-700 border-amber-200',
};

export default function MemoryDashboardPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conflicts, setConflicts] = useState<MemoryConflict[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [query, setQuery] = useState('');
  const [searchStrategy, setSearchStrategy] = useState('combined');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [consolidating, setConsolidating] = useState(false);

  const loadData = async () => {
    try {
      const [memRes, confRes, statRes] = await Promise.all([
        fetchWithAuth('/memory/'),
        fetchWithAuth('/memory/conflicts'),
        fetchWithAuth('/memory/stats'),
      ]);
      if (memRes.ok) setMemories(await memRes.json());
      if (confRes.ok) setConflicts(await confRes.json());
      if (statRes.ok) setStats(await statRes.json());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/memory/search?query=${encodeURIComponent(query)}&strategy=${searchStrategy}`);
      if (res.ok) setSearchResults(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const deleteMemory = async (id: string) => {
    if (!confirm('Delete this memory? The agent will no longer recall it.')) return;
    try {
      const res = await fetchWithAuth(`/memory/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.id !== id));
        loadData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const resolveConflict = async (id: string, keepOld: boolean) => {
    try {
      const res = await fetchWithAuth(`/memory/resolve-conflict/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resolution: `Resolved from dashboard. Kept ${keepOld ? 'original' : 'updated'} value.`,
          keep_old: keepOld,
        }),
      });
      if (res.ok) loadData();
    } catch (e) {
      console.error(e);
    }
  };

  const triggerConsolidation = async () => {
    setConsolidating(true);
    try {
      await fetchWithAuth('/memory/consolidate', { method: 'POST' });
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setConsolidating(false);
    }
  };

  const purgeAllMemory = async () => {
    if (!confirm('This permanently deletes everything the agent remembers about you. This cannot be undone. Continue?')) return;
    try {
      const res = await fetchWithAuth('/memory/forget-me', { method: 'POST' });
      if (res.ok) {
        alert('All memory deleted.');
        loadData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const unresolved = conflicts.filter((c) => !c.is_resolved).length;

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8 max-w-6xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="p-2 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-xl">
              <Database className="text-[var(--accent)] w-5 h-5" />
            </div>
            Memory
          </h1>
          <p className="text-[var(--muted)] text-sm mt-1">Everything the agent has learned about you, and how it retrieves it.</p>
        </div>
        <div className="flex gap-2.5">
          <button onClick={triggerConsolidation} disabled={consolidating} className="btn btn-secondary px-4 py-2 text-sm">
            {consolidating ? <Loader className="w-4 h-4 animate-spin" /> : null}
            Consolidate
          </button>
          <button onClick={purgeAllMemory} className="btn btn-danger px-4 py-2 text-sm">
            Delete all
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto flex flex-col gap-8">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Active memories', value: stats?.active_count ?? 0, hint: 'Currently in use', color: 'var(--foreground)' },
            { label: 'Avg. importance', value: stats ? stats.avg_importance.toFixed(2) : '0.00', hint: 'Higher = kept longer', color: 'var(--accent)' },
            { label: 'Inactive', value: stats?.inactive_count ?? 0, hint: 'Faded out over time', color: 'var(--warning)' },
            { label: 'Open conflicts', value: unresolved, hint: 'Need your decision', color: 'var(--danger)' },
          ].map((s) => (
            <div key={s.label} className="card p-5">
              <span className="text-xs font-medium text-[var(--muted)]">{s.label}</span>
              <div className="text-3xl font-bold mt-1.5" style={{ color: s.color }}>{s.value}</div>
              <div className="text-xs text-[var(--subtle)] mt-1">{s.hint}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: memories + conflicts */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            <div className="card p-6 flex flex-col gap-4">
              <h3 className="font-semibold">Stored memories</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-xs text-[var(--subtle)] uppercase font-semibold tracking-wider">
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Content</th>
                      <th className="py-2.5 px-3">Importance</th>
                      <th className="py-2.5 px-3">Uses</th>
                      <th className="py-2.5 px-3 text-right"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)] text-sm">
                    {memories.map((m) => (
                      <tr key={m.id} className="hover:bg-[var(--surface-muted)] transition-colors">
                        <td className="py-3 px-3">
                          <span className={`badge ${TYPE_STYLES[m.memory_type] ?? TYPE_STYLES.entity}`}>{m.memory_type}</span>
                        </td>
                        <td className="py-3 px-3 max-w-xs truncate text-[var(--foreground)]">{m.content}</td>
                        <td className="py-3 px-3 font-medium text-[var(--accent)]">{m.importance_score.toFixed(2)}</td>
                        <td className="py-3 px-3 text-[var(--subtle)] font-mono">{m.access_count}</td>
                        <td className="py-3 px-3 text-right">
                          <button onClick={() => deleteMemory(m.id)} className="text-[var(--subtle)] hover:text-[var(--danger)] p-1.5 rounded-lg hover:bg-[var(--danger-soft)] transition" aria-label="Delete memory">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                    {memories.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-[var(--subtle)]">
                          No memories yet. Start chatting and the agent will save what matters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Conflicts */}
            <div className="card p-6 flex flex-col gap-4">
              <h3 className="font-semibold flex items-center gap-2">
                <AlertTriangle className="text-[var(--warning)] w-4 h-4" />
                Conflicting facts
              </h3>
              <p className="text-sm text-[var(--muted)] -mt-2">When new information contradicts something stored, choose which to keep.</p>
              <div className="flex flex-col gap-4">
                {conflicts.map((c) => (
                  <div key={c.id} className="border border-[var(--border)] rounded-xl p-4 flex flex-col gap-3 text-sm bg-[var(--surface-sunken)]">
                    <div className="text-[var(--warning)] font-semibold text-xs uppercase tracking-wider">Conflict: {c.conflict_type}</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="card p-3 flex flex-col justify-between gap-3">
                        <div>
                          <span className="text-xs text-[var(--subtle)] font-semibold uppercase tracking-wider block">Original</span>
                          <p className="text-[var(--foreground)] leading-relaxed mt-1">{c.old_content}</p>
                        </div>
                        {!c.is_resolved && (
                          <button onClick={() => resolveConflict(c.id, true)} className="btn btn-secondary w-fit px-3 py-1.5 text-xs">Keep original</button>
                        )}
                      </div>
                      <div className="card p-3 flex flex-col justify-between gap-3">
                        <div>
                          <span className="text-xs text-[var(--subtle)] font-semibold uppercase tracking-wider block">New</span>
                          <p className="text-[var(--foreground)] leading-relaxed mt-1">{c.new_content}</p>
                        </div>
                        {!c.is_resolved && (
                          <button onClick={() => resolveConflict(c.id, false)} className="btn btn-primary w-fit px-3 py-1.5 text-xs">Use new</button>
                        )}
                      </div>
                    </div>
                    {c.is_resolved && (
                      <div className="text-xs text-[var(--success)] font-medium flex items-center gap-1.5 bg-[var(--success-soft)] border border-[var(--success-border)] p-2 rounded-lg w-fit">
                        <CheckCircle2 className="w-4 h-4" /> Resolved: {c.resolution}
                      </div>
                    )}
                  </div>
                ))}
                {conflicts.length === 0 && (
                  <div className="text-center text-[var(--subtle)] py-6 text-sm">No conflicts.</div>
                )}
              </div>
            </div>
          </div>

          {/* Right: search */}
          <div className="flex flex-col gap-6">
            <div className="card p-6 flex flex-col gap-4">
              <h3 className="font-semibold">Search memory</h3>
              <p className="text-sm text-[var(--muted)] -mt-2">Try different ranking strategies and compare scores.</p>
              <form onSubmit={handleSearch} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="field-label">Strategy</label>
                  <select value={searchStrategy} onChange={(e) => setSearchStrategy(e.target.value)} className="input cursor-pointer">
                    <option value="combined">Combined (recency × importance × relevance)</option>
                    <option value="semantic">Semantic similarity</option>
                    <option value="recency">Most recent</option>
                    <option value="importance">Most important</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="field-label">Query</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--subtle)]" />
                    <input type="text" required value={query} onChange={(e) => setQuery(e.target.value)} placeholder="What does the agent know about…" className="input pl-9" />
                  </div>
                </div>

                <button type="submit" disabled={loading} className="btn btn-primary py-2.5 text-sm">
                  {loading ? <Loader className="w-4 h-4 animate-spin" /> : null}
                  {loading ? 'Searching…' : 'Search'}
                </button>
              </form>

              <div className="flex flex-col gap-3 mt-2">
                <span className="text-xs text-[var(--subtle)] uppercase font-semibold tracking-wider">Results</span>
                {searchResults.map((res, idx) => (
                  <div key={idx} className="border border-[var(--border)] rounded-xl p-3 flex flex-col gap-1.5 bg-[var(--surface-sunken)]">
                    <div className="flex justify-between items-center text-xs font-mono">
                      <span className="text-[var(--accent)] font-semibold">Score {res.final_score.toFixed(3)}</span>
                      <span className="text-[var(--subtle)]">Relevance {res.relevance_score.toFixed(2)}</span>
                    </div>
                    <p className="text-sm text-[var(--foreground)] leading-relaxed">{res.memory?.content}</p>
                  </div>
                ))}
                {searchResults.length === 0 && (
                  <div className="text-[var(--subtle)] text-sm text-center py-6">No results yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
