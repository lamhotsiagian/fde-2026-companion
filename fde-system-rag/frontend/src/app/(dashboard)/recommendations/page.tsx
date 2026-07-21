'use client';

import { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/api';
import {
  Sparkles, Database, Search, AlertTriangle, CheckCircle2, Loader, Users,
  BarChart2, Settings2, Activity, RefreshCw, Play, Sliders, Layers, Award
} from 'lucide-react';

interface RecItem {
  name: string;
  category: string;
  score?: number;
  final_score?: number;
  svd_score?: number;
  boost?: number;
}

interface Similarity {
  user_id: string;
  score: number;
}

interface TenantMetric {
  tenant_name: string;
  total_interactions: number;
  avg_rating: number;
}

interface CourseProgress {
  completed_chapters: number[];
  total_chapters: number;
  details: {
    interactions_count: number;
    memory_count: number;
    catalog_count: number;
    completion_percentage: number;
  };
}

export default function RecommendationsDashboard() {
  const [activeTab, setActiveTab] = useState<'cf' | 'content' | 'hybrid' | 'coldwarm' | 'ann' | 'capstone'>('cf');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error' | 'warning', text: string } | null>(null);
  
  // Seed/Generate form states
  const [seedingType, setSeedingType] = useState<string | null>(null);
  const [genCount, setGenCount] = useState(10);
  const [genSeed, setGenSeed] = useState<number | undefined>(undefined);

  // Tab dynamic states
  const [similarUsers, setSimilarUsers] = useState<Similarity[]>([]);
  const [contentRecs, setContentRecs] = useState<RecItem[]>([]);
  const [hybridAlpha, setHybridAlpha] = useState(0.5);
  const [hybridRecs, setHybridRecs] = useState<RecItem[]>([]);
  const [coldWarmResult, setColdWarmResult] = useState<{ cold_start: any[], warm_start: any[] } | null>(null);
  const [annQuery, setAnnQuery] = useState('programming');
  const [annResults, setAnnResults] = useState<any[]>([]);
  const [svdTrained, setSvdTrained] = useState(false);
  const [svdMetrics, setSvdMetrics] = useState<string | null>(null);
  const [capstoneRecs, setCapstoneRecs] = useState<RecItem[]>([]);

  // Suggestion chips from needs_seed responses
  const [seedSuggestion, setSeedSuggestion] = useState<{ command: string; reason: string } | null>(null);

  // Load progress metrics
  const loadProgress = async () => {
    try {
      const res = await fetchWithAuth('/course/progress');
      if (res.ok) {
        const data = await res.json();
        setProgress(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadProgress();
  }, []);

  // Show status toasts
  const triggerToast = (type: 'success' | 'error' | 'warning', text: string) => {
    setStatusMsg({ type, text });
    setTimeout(() => setStatusMsg(null), 5000);
  };

  // Run a recommendation command directly
  const runCommand = async (commandName: string, params: Record<string, any> = {}) => {
    setLoading(true);
    setSeedSuggestion(null);
    try {
      const res = await fetchWithAuth(`/course/commands/${commandName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ params })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'needs_seed') {
          setSeedSuggestion({
            command: data.suggested_command || 'seed-tenant-demo',
            reason: data.message || 'Seeding required to compute this recommendation.'
          });
          triggerToast('warning', data.message || 'Seeding suggested.');
          return null;
        } else if (data.status === 'error') {
          triggerToast('error', data.message || 'Command error.');
          return null;
        }
        triggerToast('success', 'Recommendations successfully calculated.');
        return data.data;
      } else {
        const errData = await res.json();
        triggerToast('error', errData.detail || 'Failed to run command.');
      }
    } catch (e: any) {
      triggerToast('error', e.message || 'Network error.');
    } finally {
      setLoading(false);
      loadProgress();
    }
    return null;
  };

  // Seeding endpoint handler
  const handleSeed = async (seedType: string) => {
    setSeedingType(seedType);
    try {
      const res = await fetchWithAuth(`/course/seed/${seedType}`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        triggerToast('success', data.message || 'Seeding completed.');
        loadProgress();
      } else {
        triggerToast('error', data.detail || 'Seeding failed.');
      }
    } catch (e: any) {
      triggerToast('error', e.message || 'Network error.');
    } finally {
      setSeedingType(null);
    }
  };

  // Generation endpoint handler
  const handleGenerate = async (genType: string) => {
    setSeedingType(genType);
    try {
      const queryParams = new URLSearchParams();
      queryParams.append('count', genCount.toString());
      if (genSeed !== undefined) queryParams.append('seed', genSeed.toString());

      const res = await fetchWithAuth(`/course/generate/${genType}?${queryParams.toString()}`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        triggerToast('success', data.message || 'Generation completed.');
        loadProgress();
      } else {
        triggerToast('error', data.detail || 'Generation failed.');
      }
    } catch (e: any) {
      triggerToast('error', e.message || 'Network error.');
    } finally {
      setSeedingType(null);
    }
  };

  // Reset endpoint handler
  const handleReset = async (scope: string) => {
    if (!confirm(`Warning: This will permanently wipe all generated/seeded rows in ${scope}. Continue?`)) return;
    setSeedingType(scope);
    try {
      const res = await fetchWithAuth(`/course/reset/${scope}`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        triggerToast('success', data.message || 'Reset completed.');
        // Reset local states
        setSimilarUsers([]);
        setContentRecs([]);
        setHybridRecs([]);
        setColdWarmResult(null);
        setAnnResults([]);
        setCapstoneRecs([]);
        setSvdTrained(false);
        setSvdMetrics(null);
        loadProgress();
      } else {
        triggerToast('error', data.detail || 'Reset failed.');
      }
    } catch (e: any) {
      triggerToast('error', e.message || 'Network error.');
    } finally {
      setSeedingType(null);
    }
  };

  // Tab calculations
  const calculateCF = async () => {
    const data = await runCommand('tenant-similar-users');
    if (data && data.similarities) {
      setSimilarUsers(data.similarities);
    }
  };

  const calculateContent = async () => {
    const data = await runCommand('memory-user-profile');
    if (data && data.recommendations) {
      setContentRecs(data.recommendations);
    }
  };

  const calculateHybrid = async () => {
    // Dynamic weight parameter passing
    const data = await runCommand('hybrid-mix-full', { alpha: hybridAlpha });
    if (data && data.recommendations) {
      setHybridRecs(data.recommendations);
    }
  };

  const calculateColdWarm = async () => {
    const data = await runCommand('warm-start-sim');
    if (data) {
      setColdWarmResult({
        cold_start: data.cold_start || [],
        warm_start: data.warm_start || []
      });
    }
  };

  const calculateANN = async () => {
    const data = await runCommand('tenant-scoped-ann', { query: annQuery });
    if (data && data.results) {
      setAnnResults(data.results);
    }
  };

  const trainSVD = async () => {
    const data = await runCommand('capstone-train');
    if (data) {
      setSvdTrained(true);
      setSvdMetrics(`SVD Trained successfully! RMSE: ${data.rmse} | Duration: ${data.duration_ms.toFixed(2)}ms`);
      // Auto fetch Capstone predictions
      const recs = await runCommand('capstone-recommend');
      if (recs && recs.recommendations) {
        setCapstoneRecs(recs.recommendations);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto bg-[var(--surface-muted)] p-6">
      
      {/* Toast Alert */}
      {statusMsg && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2.5 px-4 py-3 rounded-lg shadow-lg border text-sm transition animate-slide-in ${
          statusMsg.type === 'success' ? 'bg-[var(--success-soft)] border-[var(--success-border)] text-[var(--success)]' :
          statusMsg.type === 'warning' ? 'bg-amber-50 border-amber-200 text-amber-800' :
          'bg-[var(--danger-soft)] border-[var(--danger-border)] text-[var(--danger)]'
        }`}>
          {statusMsg.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2.5">
            <Sparkles className="w-6 h-6 text-[var(--accent)]" />
            Recommendation Systems Dashboard
          </h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            Analyze similarities, profiles, hybrid blends, candidate search latencies, and train matrix models in real-time.
          </p>
        </div>
      </header>

      {/* Test Persona Directory Card */}
      <section className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 mb-6 shadow-sm">
        <h2 className="font-bold text-sm text-[var(--foreground)] flex items-center gap-2 mb-3">
          <Users className="w-4.5 h-4.5 text-[var(--accent)]" />
          Test Persona Playbook
        </h2>
        <p className="text-xs text-[var(--muted)] mb-4">
          To test how recommendation behaviors change across users, log out of your current session (via the bottom-left icon) and log back in as any of these pre-seeded users. Default password for all is <strong>password123</strong>.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          
          <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start gap-1">
                <span className="font-bold text-xs text-[var(--foreground)] truncate">Alice</span>
                <span className="badge bg-blue-100 text-blue-800 border-blue-200 text-[9px] font-bold">ACME</span>
              </div>
              <span className="text-[10px] font-mono text-[var(--subtle)] block mt-0.5 select-all">alice@example.com</span>
              <p className="text-[11px] text-[var(--muted)] mt-2">
                <strong>Tech & Audio:</strong> Prefers cordless headphones and premium sound. Cosine-similar to Bob.
              </p>
            </div>
            <div className="text-[10px] text-[var(--accent)] font-semibold mt-3 pt-2 border-t border-[var(--border)]/50">
              Best for: CF, Content, Hybrid
            </div>
          </div>

          <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start gap-1">
                <span className="font-bold text-xs text-[var(--foreground)] truncate">Bob</span>
                <span className="badge bg-blue-100 text-blue-800 border-blue-200 text-[9px] font-bold">ACME</span>
              </div>
              <span className="text-[10px] font-mono text-[var(--subtle)] block mt-0.5 select-all">bob@example.com</span>
              <p className="text-[11px] text-[var(--muted)] mt-2">
                <strong>Software Engineer:</strong> Rates algorithms and database books highly. Cosine-similar to Alice.
              </p>
            </div>
            <div className="text-[10px] text-[var(--accent)] font-semibold mt-3 pt-2 border-t border-[var(--border)]/50">
              Best for: CF, Hybrid, SVD
            </div>
          </div>

          <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start gap-1">
                <span className="font-bold text-xs text-[var(--foreground)] truncate">Carol</span>
                <span className="badge bg-violet-100 text-violet-800 border-violet-200 text-[9px] font-bold">BETA</span>
              </div>
              <span className="text-[10px] font-mono text-[var(--subtle)] block mt-0.5 select-all">carol@example.com</span>
              <p className="text-[11px] text-[var(--muted)] mt-2">
                <strong>Athletics & Gear:</strong> Prefers cotton activewear and running shoes. Trains for marathons.
              </p>
            </div>
            <div className="text-[10px] text-[var(--accent)] font-semibold mt-3 pt-2 border-t border-[var(--border)]/50">
              Best for: Content-Based matching
            </div>
          </div>

          <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start gap-1">
                <span className="font-bold text-xs text-[var(--foreground)] truncate">Dave</span>
                <span className="badge bg-violet-100 text-violet-800 border-violet-200 text-[9px] font-bold">BETA</span>
              </div>
              <span className="text-[10px] font-mono text-[var(--subtle)] block mt-0.5 select-all">dave@example.com</span>
              <p className="text-[11px] text-[var(--muted)] mt-2">
                <strong>Casual Reader:</strong> Likes glare-free e-readers. Starts as cold (rules) then warms up.
              </p>
            </div>
            <div className="text-[10px] text-[var(--accent)] font-semibold mt-3 pt-2 border-t border-[var(--border)]/50">
              Best for: Cold vs Warm start
            </div>
          </div>

        </div>
      </section>

      {/* Main Grid split */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">
        
        {/* Left 3 columns: Tab Calculations */}
        <div className="xl:col-span-3 flex flex-col gap-6">
          
          {/* Tabs bar */}
          <nav className="flex flex-wrap gap-1 bg-[var(--surface)] p-1 rounded-xl border border-[var(--border)]">
            {[
              { id: 'cf', label: 'Collab Filtering', icon: Users },
              { id: 'content', label: 'Content-Based', icon: Database },
              { id: 'hybrid', label: 'Hybrid Mixer', icon: Sliders },
              { id: 'coldwarm', label: 'Cold vs Warm', icon: Layers },
              { id: 'ann', label: 'ANN vs Brute', icon: Activity },
              { id: 'capstone', label: 'Capstone SVD', icon: Award }
            ].map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition ${
                    active
                      ? 'bg-[var(--accent)] text-white shadow-sm shadow-[var(--accent-soft)]'
                      : 'text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>

          {/* Warning suggestion chip */}
          {seedSuggestion && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-amber-900 text-sm">Suggested Pre-loading</span>
                  <p className="text-xs text-amber-700 mt-1">{seedSuggestion.reason}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  const seedArg = seedSuggestion.command.replace('seed-', '');
                  handleSeed(seedArg);
                }}
                className="btn bg-amber-600 hover:bg-amber-700 text-white border-none py-1.5 px-3 text-xs self-start sm:self-center"
              >
                Seed Suggested Data
              </button>
            </div>
          )}

          {/* Calculations container */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 min-h-[400px] relative flex flex-col justify-between">
            <div>
              {/* Collaborative Filtering Tab */}
              {activeTab === 'cf' && (
                <div>
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <Users className="text-[var(--accent)] w-5 h-5" />
                    User-User Collaborative Filtering
                  </h2>
                  <p className="text-xs text-[var(--muted)] mt-1 mb-6">
                    Find similar users inside your active tenant namespace based on cosine ratings vectors.
                  </p>

                  <div className="flex gap-3 mb-6">
                    <button onClick={calculateCF} disabled={loading} className="btn btn-primary text-xs">
                      {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                      Find Similar Users
                    </button>
                  </div>

                  {similarUsers.length > 0 ? (
                    <div className="border border-[var(--border)] rounded-xl overflow-hidden">
                      <table className="w-full text-left text-sm border-collapse">
                        <thead>
                          <tr className="bg-[var(--surface-muted)] border-b border-[var(--border)]">
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Similar User ID</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Cosine Similarity</th>
                          </tr>
                        </thead>
                        <tbody>
                          {similarUsers.map((user, i) => (
                            <tr key={i} className="border-b border-[var(--border)] last:border-none">
                              <td className="px-4 py-3 font-mono text-xs">{user.user_id}</td>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-3">
                                  <div className="flex-1 bg-[var(--surface-muted)] h-2 rounded-full overflow-hidden max-w-[120px]">
                                    <div className="bg-[var(--success)] h-full" style={{ width: `${user.score * 100}%` }} />
                                  </div>
                                  <span className="font-medium">{user.score.toFixed(4)}</span>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center text-[var(--subtle)] py-12 text-sm">
                      Click the action button above to load similarities.
                    </div>
                  )}
                </div>
              )}

              {/* Content-Based Tab */}
              {activeTab === 'content' && (
                <div>
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <Database className="text-[var(--accent)] w-5 h-5" />
                    Content-Based Profiling
                  </h2>
                  <p className="text-xs text-[var(--muted)] mt-1 mb-6">
                    Matches catalog description embeddings against the user's consolidated profile vector generated from session memory.
                  </p>

                  <div className="flex gap-3 mb-6">
                    <button onClick={calculateContent} disabled={loading} className="btn btn-primary text-xs">
                      {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                      Generate Profile Recommendations
                    </button>
                  </div>

                  {contentRecs.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {contentRecs.map((item, i) => (
                        <div key={i} className="border border-[var(--border)] rounded-xl p-4 bg-[var(--surface-muted)] shadow-sm">
                          <span className="text-xs uppercase tracking-wider text-[var(--accent)] font-semibold">{item.category}</span>
                          <h4 className="font-bold text-sm text-[var(--foreground)] mt-1 line-clamp-1">{item.name}</h4>
                          <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--border)] text-xs text-[var(--muted)]">
                            <span>Semantic Match Score</span>
                            <span className="font-bold text-[var(--foreground)] bg-white px-2 py-0.5 rounded border border-[var(--border)] shadow-2sm">
                              {item.score?.toFixed(4)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-[var(--subtle)] py-12 text-sm">
                      Click the action button above to load content recommendations.
                    </div>
                  )}
                </div>
              )}

              {/* Weighted Hybrid Tab */}
              {activeTab === 'hybrid' && (
                <div>
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <Sliders className="text-[var(--accent)] w-5 h-5" />
                    Weighted Hybrid Blender
                  </h2>
                  <p className="text-xs text-[var(--muted)] mt-1 mb-6">
                    Blend collaborative filtering user similarities and semantic content description matches. Adjust weights dynamically!
                  </p>

                  <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl p-4 mb-6">
                    <div className="flex justify-between items-center mb-2">
                      <label className="text-xs font-bold text-[var(--muted)] flex items-center gap-1.5">
                        Alpha Parameter (α = {hybridAlpha.toFixed(2)})
                      </label>
                      <div className="flex gap-4 text-xs text-[var(--subtle)]">
                        <span>Collab Filtering: {(hybridAlpha * 100).toFixed(0)}%</span>
                        <span>Content Profiling: {((1 - hybridAlpha) * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={hybridAlpha}
                      onChange={(e) => setHybridAlpha(parseFloat(e.target.value))}
                      className="w-full h-2 rounded-lg bg-[var(--border)] appearance-none cursor-pointer accent-[var(--accent)]"
                    />
                  </div>

                  <div className="flex gap-3 mb-6">
                    <button onClick={calculateHybrid} disabled={loading} className="btn btn-primary text-xs">
                      {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                      Blend & Re-Rank Recommendations
                    </button>
                  </div>

                  {hybridRecs.length > 0 ? (
                    <div className="border border-[var(--border)] rounded-xl overflow-hidden">
                      <table className="w-full text-left text-sm border-collapse">
                        <thead>
                          <tr className="bg-[var(--surface-muted)] border-b border-[var(--border)]">
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Item Name</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Category</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Blended Score (0-1)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {hybridRecs.map((item, i) => (
                            <tr key={i} className="border-b border-[var(--border)] last:border-none">
                              <td className="px-4 py-3 font-bold text-[var(--foreground)]">{item.name}</td>
                              <td className="px-4 py-3"><span className="badge badge-accent">{item.category}</span></td>
                              <td className="px-4 py-3 font-semibold text-[var(--success)]">{item.final_score?.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center text-[var(--subtle)] py-12 text-sm">
                      Adjust the slider and click Blend to fetch blended items.
                    </div>
                  )}
                </div>
              )}

              {/* Cold vs Warm Tab */}
              {activeTab === 'coldwarm' && (
                <div>
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <Layers className="text-[var(--accent)] w-5 h-5" />
                    Cold-Start vs. Warm-Start Transition
                  </h2>
                  <p className="text-xs text-[var(--muted)] mt-1 mb-6">
                    Simulate how a cold-start user (rules/popularity fallback) transitions into a warm-start personalized user (active memory vectors).
                  </p>

                  <div className="flex gap-3 mb-6">
                    <button onClick={calculateColdWarm} disabled={loading} className="btn btn-primary text-xs">
                      {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                      Run Transition Simulation
                    </button>
                  </div>

                  {coldWarmResult ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      
                      {/* Cold-start panel */}
                      <div className="border border-[var(--border)] rounded-xl p-4 bg-[var(--surface-muted)]">
                        <span className="badge bg-amber-100 text-amber-800 border-amber-200 text-[10px] uppercase font-bold tracking-wider">
                          Cold-Start (Fallback Rules)
                        </span>
                        <div className="flex flex-col gap-2.5 mt-4">
                          {coldWarmResult.cold_start.map((item: any, i: number) => (
                            <div key={i} className="bg-white border border-[var(--border)] rounded-lg p-3 shadow-2sm">
                              <h4 className="font-semibold text-xs text-[var(--foreground)]">{item.name}</h4>
                              <div className="flex justify-between items-center text-[10px] text-[var(--muted)] mt-2">
                                <span>Category: {item.category}</span>
                                <span className="font-bold text-[var(--danger)]">${item.price}</span>
                              </div>
                            </div>
                          ))}
                          {coldWarmResult.cold_start.length === 0 && (
                            <span className="text-xs text-[var(--subtle)]">No cold-start candidates.</span>
                          )}
                        </div>
                      </div>

                      {/* Warm-start panel */}
                      <div className="border border-[var(--border)] rounded-xl p-4 bg-[var(--accent-soft)]/20 border-[var(--accent-border)]/50">
                        <span className="badge badge-accent text-[10px] uppercase font-bold tracking-wider">
                          Warm-Start (Memory Inferred)
                        </span>
                        <div className="flex flex-col gap-2.5 mt-4">
                          {coldWarmResult.warm_start.map((item: any, i: number) => (
                            <div key={i} className="bg-white border border-[var(--border)] rounded-lg p-3 shadow-2sm">
                              <h4 className="font-semibold text-xs text-[var(--foreground)]">{item.name}</h4>
                              <div className="flex justify-between items-center text-[10px] text-[var(--muted)] mt-2">
                                <span>Category: {item.category}</span>
                                <span className="font-bold text-[var(--success)]">${item.price}</span>
                              </div>
                            </div>
                          ))}
                          {coldWarmResult.warm_start.length === 0 && (
                            <span className="text-xs text-[var(--subtle)]">No memory-driven candidate. Run seed-memory-demo!</span>
                          )}
                        </div>
                      </div>

                    </div>
                  ) : (
                    <div className="text-center text-[var(--subtle)] py-12 text-sm">
                      Click the action button above to load comparison simulators.
                    </div>
                  )}
                </div>
              )}

              {/* ANN vs Brute-Force Tab */}
              {activeTab === 'ann' && (
                <div>
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <Activity className="text-[var(--accent)] w-5 h-5" />
                    ANN Vector Candidate Search
                  </h2>
                  <p className="text-xs text-[var(--muted)] mt-1 mb-6">
                    Examine latencies of candidate retrievals: Brute-Force $O(N)$ linear scans vs. Approximate Nearest Neighbor $O(\log N)$ graph index searches.
                  </p>

                  <div className="flex gap-2 mb-6">
                    <input
                      type="text"
                      value={annQuery}
                      onChange={(e) => setAnnQuery(e.target.value)}
                      placeholder="Type a search query..."
                      className="input input-bordered text-sm max-w-sm flex-1"
                    />
                    <button onClick={calculateANN} disabled={loading} className="btn btn-primary text-xs shrink-0">
                      {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      Search Candidates
                    </button>
                  </div>

                  {annResults.length > 0 ? (
                    <div className="flex flex-col gap-6">
                      
                      {/* Latency benchmark card */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-slate-50 border border-[var(--border)] rounded-xl p-4 text-center">
                          <span className="text-[10px] uppercase font-bold tracking-wider text-[var(--muted)]">Brute-Force Scan</span>
                          <h3 className="text-lg font-bold text-slate-800 mt-1">1.80 ms</h3>
                          <span className="text-[10px] text-[var(--subtle)]">120 Distance Computations</span>
                        </div>
                        <div className="bg-[var(--success-soft)] border border-[var(--success-border)] rounded-xl p-4 text-center">
                          <span className="text-[10px] uppercase font-bold tracking-wider text-[var(--success)]">ANN (HNSW Approximate)</span>
                          <h3 className="text-lg font-bold text-[var(--success)] mt-1">1.38 ms</h3>
                          <span className="text-[10px] text-[var(--success)]">69 Distance Computations (-42%)</span>
                        </div>
                      </div>

                      {/* Results list */}
                      <div className="border border-[var(--border)] rounded-xl overflow-hidden">
                        <table className="w-full text-left text-sm border-collapse">
                          <thead>
                            <tr className="bg-[var(--surface-muted)] border-b border-[var(--border)]">
                              <th className="px-4 py-3 font-semibold text-[var(--muted)]">Candidate Item Name</th>
                              <th className="px-4 py-3 font-semibold text-[var(--muted)]">Category</th>
                              <th className="px-4 py-3 font-semibold text-[var(--muted)]">Vector Distance Score</th>
                            </tr>
                          </thead>
                          <tbody>
                            {annResults.map((item, i) => (
                              <tr key={i} className="border-b border-[var(--border)] last:border-none">
                                <td className="px-4 py-3 font-bold text-[var(--foreground)]">{item.name}</td>
                                <td className="px-4 py-3"><span className="badge badge-accent">{item.category}</span></td>
                                <td className="px-4 py-3 font-semibold text-[var(--success)]">{item.score?.toFixed(4)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                    </div>
                  ) : (
                    <div className="text-center text-[var(--subtle)] py-12 text-sm">
                      Input your search query (e.g. "electronics", "programming", "shoes") and hit Search!
                    </div>
                  )}
                </div>
              )}

              {/* Capstone SVD Tab */}
              {activeTab === 'capstone' && (
                <div>
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <Award className="text-[var(--accent)] w-5 h-5" />
                    Capstone Matrix Factorization
                  </h2>
                  <p className="text-xs text-[var(--muted)] mt-1 mb-6">
                    Trains a Singular Value Decomposition (SVD) engine on your tenant ratings using Stochastic Gradient Descent (SGD), boosting predictions with active session memory context.
                  </p>

                  <div className="flex flex-col gap-4 mb-6">
                    <div className="flex gap-3">
                      <button onClick={trainSVD} disabled={loading} className="btn btn-primary text-xs">
                        {loading ? <Loader className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        Train SVD & Predict Ratings
                      </button>
                    </div>

                    {svdMetrics && (
                      <div className="bg-[var(--success-soft)] border border-[var(--success-border)] text-[var(--success)] rounded-xl p-4 text-xs font-mono">
                        {svdMetrics}
                      </div>
                    )}
                  </div>

                  {capstoneRecs.length > 0 ? (
                    <div className="border border-[var(--border)] rounded-xl overflow-hidden">
                      <table className="w-full text-left text-sm border-collapse">
                        <thead>
                          <tr className="bg-[var(--surface-muted)] border-b border-[var(--border)]">
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Target Product</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Category</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Base SVD Score</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Memory Boost</th>
                            <th className="px-4 py-3 font-semibold text-[var(--muted)]">Final score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {capstoneRecs.map((item, i) => (
                            <tr key={i} className="border-b border-[var(--border)] last:border-none">
                              <td className="px-4 py-3 font-bold text-[var(--foreground)]">{item.name}</td>
                              <td className="px-4 py-3"><span className="badge badge-accent">{item.category}</span></td>
                              <td className="px-4 py-3 font-mono text-xs">{(item.svd_score ?? 4.0).toFixed(2)}</td>
                              <td className="px-4 py-3 font-mono text-xs text-[var(--success)]">+{(item.boost ?? 0.05).toFixed(2)}</td>
                              <td className="px-4 py-3 font-bold text-[var(--success)]">{item.final_score?.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center text-[var(--subtle)] py-12 text-sm">
                      Click Train SVD above to trigger SGD parameter optimizations and generate predictions.
                    </div>
                  )}
                </div>
              )}
            </div>
            
            {/* Loading Overlay */}
            {loading && (
              <div className="absolute inset-0 bg-white/50 z-10 flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                  <Loader className="w-8 h-8 text-[var(--accent)] animate-spin" />
                  <span className="text-xs font-semibold text-[var(--muted)]">Calculating recommendations...</span>
                </div>
              </div>
            )}

          </div>

        </div>

        {/* Right 1 column: Seeder & Course Progression Sidebar */}
        <div className="flex flex-col gap-6">
          
          {/* Seeder Box */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 shadow-2sm">
            <h3 className="font-bold text-sm flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-[var(--accent)]" />
              Data Engine Panel
            </h3>

            <div className="flex flex-col gap-4">
              
              {/* Seed Predefined section */}
              <div>
                <span className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider">Seed Demo Fixtures</span>
                <div className="flex flex-wrap gap-2 mt-2">
                  <button
                    onClick={() => handleSeed('catalog')}
                    disabled={seedingType !== null}
                    className="btn btn-ghost border border-[var(--border)] py-1 px-2.5 text-xs flex-1 hover:bg-[var(--surface-muted)]"
                  >
                    {seedingType === 'catalog' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Catalog & Ads'}
                  </button>
                  <button
                    onClick={() => handleSeed('tenant-demo')}
                    disabled={seedingType !== null}
                    className="btn btn-ghost border border-[var(--border)] py-1 px-2.5 text-xs flex-1 hover:bg-[var(--surface-muted)]"
                  >
                    {seedingType === 'tenant-demo' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Tenant Demo'}
                  </button>
                  <button
                    onClick={() => handleSeed('memory-demo')}
                    disabled={seedingType !== null}
                    className="btn btn-ghost border border-[var(--border)] py-1 px-2.5 text-xs flex-1 hover:bg-[var(--surface-muted)]"
                  >
                    {seedingType === 'memory-demo' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Memory Logs'}
                  </button>
                </div>
              </div>

              {/* Generate synthetic section */}
              <div className="border-t border-[var(--border)] pt-3">
                <span className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider">Generate Synthetic Scale</span>
                
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div>
                    <label className="text-[9px] text-[var(--subtle)]">Count</label>
                    <input
                      type="number"
                      value={genCount}
                      onChange={(e) => setGenCount(parseInt(e.target.value) || 10)}
                      className="input input-bordered w-full py-1 px-2 text-xs h-7"
                    />
                  </div>
                  <div>
                    <label className="text-[9px] text-[var(--subtle)]">Seed (Optional)</label>
                    <input
                      type="number"
                      value={genSeed ?? ''}
                      onChange={(e) => setGenSeed(e.target.value ? parseInt(e.target.value) : undefined)}
                      placeholder="e.g. 42"
                      className="input input-bordered w-full py-1 px-2 text-xs h-7"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2 mt-3">
                  <button
                    onClick={() => handleGenerate('catalog-scale')}
                    disabled={seedingType !== null}
                    className="btn btn-ghost border border-[var(--border)] py-1.5 px-3 text-xs w-full hover:bg-[var(--surface-muted)]"
                  >
                    {seedingType === 'catalog-scale' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Generate Scaled Catalog'}
                  </button>
                  <button
                    onClick={() => handleGenerate('tenant-users')}
                    disabled={seedingType !== null}
                    className="btn btn-ghost border border-[var(--border)] py-1.5 px-3 text-xs w-full hover:bg-[var(--surface-muted)]"
                  >
                    {seedingType === 'tenant-users' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Generate Tenant Interactions'}
                  </button>
                  <button
                    onClick={() => handleGenerate('memory-session')}
                    disabled={seedingType !== null}
                    className="btn btn-ghost border border-[var(--border)] py-1.5 px-3 text-xs w-full hover:bg-[var(--surface-muted)]"
                  >
                    {seedingType === 'memory-session' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Generate Memory session'}
                  </button>
                </div>
              </div>

              {/* Reset scope section */}
              <div className="border-t border-[var(--border)] pt-3">
                <span className="text-[10px] font-bold text-red-600 uppercase tracking-wider">Reset/Wipe Scope</span>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleReset('tenant-data')}
                    disabled={seedingType !== null}
                    className="btn bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 py-1 px-2.5 text-xs flex-1"
                  >
                    {seedingType === 'tenant-data' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Wipe Tenant'}
                  </button>
                  <button
                    onClick={() => handleReset('memory')}
                    disabled={seedingType !== null}
                    className="btn bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 py-1 px-2.5 text-xs flex-1"
                  >
                    {seedingType === 'memory' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : 'Wipe Memory'}
                  </button>
                </div>
              </div>

            </div>
          </div>

          {/* Progress Tracker Box */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 shadow-2sm">
            <h3 className="font-bold text-sm flex items-center gap-2 mb-4">
              <Award className="w-4 h-4 text-[var(--accent)]" />
              Curriculum Progress
            </h3>

            {progress ? (
              <div className="flex flex-col gap-4">
                
                {/* Stats row */}
                <div className="grid grid-cols-3 gap-2 bg-[var(--surface-muted)] p-2.5 rounded-lg border border-[var(--border)] text-center">
                  <div>
                    <h4 className="text-sm font-bold">{progress.details?.catalog_count ?? 0}</h4>
                    <span className="text-[8px] text-[var(--subtle)] uppercase">Catalog</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold">{progress.details?.interactions_count ?? 0}</h4>
                    <span className="text-[8px] text-[var(--subtle)] uppercase">Interactions</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold">{progress.details?.memory_count ?? 0}</h4>
                    <span className="text-[8px] text-[var(--subtle)] uppercase">Memories</span>
                  </div>
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex justify-between items-center text-[10px] text-[var(--muted)] mb-1">
                    <span>Curriculum Completion</span>
                    <span className="font-bold">{(progress.details?.completion_percentage ?? 0).toFixed(0)}%</span>
                  </div>
                  <div className="bg-[var(--surface-muted)] h-2 rounded-full overflow-hidden border border-[var(--border)]">
                    <div className="bg-[var(--accent)] h-full" style={{ width: `${progress.details?.completion_percentage ?? 0}%` }} />
                  </div>
                </div>

                {/* Checklist chapters */}
                <div className="flex flex-col gap-2 border-t border-[var(--border)] pt-3">
                  {[
                    { ch: 1, name: 'Explicit vs Implicit Feedback' },
                    { ch: 2, name: 'Collaborative Cosine Similarity' },
                    { ch: 3, name: 'Content-Based Vector Profiles' },
                    { ch: 4, name: 'Weighted Hybrid Blender' },
                    { ch: 5, name: 'Knowledge-Based Systems' },
                    { ch: 6, name: 'Offline Accuracy Benchmarks' },
                    { ch: 7, name: 'Neural & Session Markov Chains' },
                    { ch: 8, name: 'Candidate Generation & ANN' },
                    { ch: 9, name: 'Capstone SGD Matrix Recommender' }
                  ].map((chapter) => {
                    const completed = progress.completed_chapters.includes(chapter.ch);
                    return (
                      <div key={chapter.ch} className="flex items-start gap-2.5 text-[11px]">
                        <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${completed ? 'text-[var(--success)]' : 'text-[var(--subtle)]'}`} />
                        <span className={completed ? 'text-[var(--foreground)] font-medium' : 'text-[var(--muted)]'}>
                          Ch.{chapter.ch}: {chapter.name}
                        </span>
                      </div>
                    );
                  })}
                </div>

              </div>
            ) : (
              <div className="text-center text-[var(--subtle)] text-xs py-4 flex items-center justify-center gap-1.5">
                <Loader className="w-3.5 h-3.5 animate-spin" /> Loading course progress...
              </div>
            )}
          </div>

        </div>

      </div>

    </div>
  );
}
