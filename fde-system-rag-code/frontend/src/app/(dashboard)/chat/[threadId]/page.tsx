'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState, useRef } from 'react';
import { fetchWithAuth, BACKEND_URL } from '@/lib/api';
import { Message } from '@/lib/types';
import { 
  Send, 
  Loader, 
  User, 
  Cpu, 
  Upload, 
  Check, 
  BrainCircuit, 
  Terminal, 
  Award, 
  CheckCircle2, 
  BookOpen, 
  ChevronRight,
  HelpCircle,
  Settings,
  X
} from 'lucide-react';

const SLASH_COMMANDS = [
  { name: '/ingest-status', desc: 'Check document ingestion pipeline status' },
  { name: '/hybrid-search', desc: 'Perform BM25 + pgvector hybrid retrieval' },
  { name: '/rerank-docs', desc: 'Re-rank retrieved context with cross-encoder' },
  { name: '/agent-state', desc: 'View active LangGraph StateGraph nodes' },
  { name: '/tenant-info', desc: 'View multi-tenant isolation context' },
];

export default function ChatWindowPage() {
  const params = useParams();
  const threadId = params.threadId as string;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [activeInterrupt, setActiveInterrupt] = useState<any | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [toolLogs, setToolLogs] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [uploadedDocs, setUploadedDocs] = useState<any[]>([]);

  // Autocomplete state
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  
  // Progress modal state
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [courseProgress, setCourseProgress] = useState<any>(null);
  const [loadingProgress, setLoadingProgress] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, toolLogs]);

  const loadHistory = async () => {
    try {
      const res = await fetchWithAuth(`/chat/${threadId}`);
      if (res.ok) {
        const history = await res.json();
        setMessages(
          history.map((m: { role: string; content: string }) => ({
            role: m.role === 'human' ? 'human' : 'ai',
            content: m.content,
          }))
        );
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadDocuments = async () => {
    try {
      const res = await fetchWithAuth(`/documents/${threadId}`);
      if (res.ok) {
        const docs = await res.json();
        setUploadedDocs(docs);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (threadId) {
      loadHistory();
      loadDocuments();
      setToolLogs([]);
      setStreamingContent('');
    }
  }, [threadId]);

  // Execute a command directly
  const executeCommand = async (commandStr: string) => {
    const cleanCmd = commandStr.trim();
    const userMessage: Message = { role: 'human', content: cleanCmd };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setToolLogs([]);
    setStreamingContent('');
    setActiveInterrupt(null);

    let accumulated = '';
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`${BACKEND_URL}/chat/${threadId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ prompt: cleanCmd, model_name: 'llama3.1' }),
      });

      if (!res.ok) throw new Error('Streaming connection failed');

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buffer = '';
      let isInterrupted = false;
      let interruptData: any = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.type === 'llm_chunk') {
              accumulated += data.content;
              setStreamingContent(accumulated);
            } else if (data.type === 'interrupt') {
              isInterrupted = true;
              interruptData = data;
              break;
            }
          } catch {
            // ignore
          }
        }
        if (isInterrupted) break;
      }

      if (isInterrupted && interruptData) {
        setActiveInterrupt(interruptData);
      } else {
        setMessages((prev) => [...prev, { role: 'ai', content: accumulated || '(No response received.)' }]);
      }
      setStreamingContent('');
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'ai', content: `Error running command: ${err}` }
      ]);
      setStreamingContent('');
    } finally {
      setLoading(false);
    }
  };

  const handleInterruptResponse = async (approved: boolean) => {
    if (!activeInterrupt) return;
    setLoading(true);
    const token = localStorage.getItem('access_token');
    
    const actionText = approved ? 'Confirming execution...' : 'Cancelling execution...';
    setMessages((prev) => [...prev, { role: 'system', content: actionText }]);
    
    setActiveInterrupt(null);
    setStreamingContent('');

    let accumulated = '';
    try {
      const res = await fetch(`${BACKEND_URL}/chat/${threadId}/resume?approved=${approved}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) throw new Error('Resuming connection failed');

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buffer = '';
      let isInterrupted = false;
      let interruptData: any = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.type === 'llm_chunk') {
              accumulated += data.content;
              setStreamingContent(accumulated);
            } else if (data.type === 'interrupt') {
              isInterrupted = true;
              interruptData = data;
              break;
            }
          } catch {
            // ignore
          }
        }
        if (isInterrupted) break;
      }

      if (isInterrupted && interruptData) {
        setActiveInterrupt(interruptData);
      } else {
        setMessages((prev) => [...prev, { role: 'ai', content: accumulated || '(No response received.)' }]);
      }
      setStreamingContent('');
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'ai', content: `Error running command: ${err}` }
      ]);
      setStreamingContent('');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const currentInput = input;
    setInput('');
    setShowAutocomplete(false);
    await executeCommand(currentInput);
  };

  const handleInputChange = (val: string) => {
    setInput(val);
    if (val.startsWith('/')) {
      setShowAutocomplete(true);
    } else {
      setShowAutocomplete(false);
    }
  };

  const loadProgressDetails = async () => {
    setLoadingProgress(true);
    try {
      const res = await fetchWithAuth('/course/progress');
      if (res.ok) {
        const prog = await res.json();
        setCourseProgress(prog);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingProgress(false);
    }
  };

  useEffect(() => {
    if (showProgressModal) {
      loadProgressDetails();
    }
  }, [showProgressModal]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadNotice('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`${BACKEND_URL}/documents/upload/${threadId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (res.ok) {
        setUploadNotice(`Indexed "${file.name}" — the agent can now reference it.`);
        loadDocuments();
        setTimeout(() => setUploadNotice(''), 4000);
      } else {
        alert('File upload failed.');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Autocomplete matching list
  const filteredCommands = SLASH_COMMANDS.filter(cmd => 
    cmd.name.toLowerCase().startsWith(input.toLowerCase())
  );

  // Helper to extract seed suggestions
  const getSuggestions = (text: string) => {
    const seedCommands = [
      '/seed-tenant-demo',
      '/seed-memory-demo',
      '/seed-catalog',
      '/capstone-train'
    ];
    return seedCommands.filter(cmd => text.includes(cmd));
  };

  // Premium table and content renderer
  const renderMessageContent = (content: string) => {
    if (content.includes('|')) {
      const lines = content.split('\n');
      const tableLines = lines.filter(l => l.trim().startsWith('|'));
      if (tableLines.length >= 2) {
        try {
          const headers = tableLines[0].split('|').map(s => s.trim()).filter(Boolean);
          const rows = tableLines.slice(2).map(line => {
            return line.split('|').map(s => s.trim()).filter(Boolean);
          }).filter(r => r.length > 0 && !r.every(c => c.startsWith('-')));

          const nonTableText = lines.filter(l => !l.trim().startsWith('|')).join('\n');

          return (
            <div className="flex flex-col gap-3">
              {nonTableText && <div className="whitespace-pre-wrap">{nonTableText}</div>}
              <div className="overflow-hidden my-2.5 rounded-xl border border-[var(--border)] shadow-sm bg-[var(--surface)]">
                <table className="min-w-full divide-y divide-[var(--border)] text-xs text-left">
                  <thead className="bg-[var(--surface-muted)] font-semibold text-[var(--muted)] uppercase tracking-wider">
                    <tr>
                      {headers.map((h, i) => (
                        <th key={i} className="px-4 py-2.5 font-semibold text-[10px]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {rows.map((row, rIdx) => (
                      <tr key={rIdx} className={rIdx % 2 === 0 ? 'bg-white hover:bg-slate-50/50' : 'bg-slate-50/30 hover:bg-slate-50/50'}>
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="px-4 py-2.5 font-medium whitespace-pre-wrap text-[var(--foreground)]">
                            {cell.startsWith('/') ? (
                              <button
                                onClick={() => executeCommand(cell)}
                                className="font-mono text-[var(--accent)] hover:underline cursor-pointer bg-[var(--accent-soft)] px-2 py-0.5 rounded-md border border-[var(--accent-border)] font-bold text-[10px]"
                              >
                                {cell}
                              </button>
                            ) : (
                              cell
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        } catch (err) {
          console.error("Failed parsing markdown table:", err);
        }
      }
    }

    // Default text formatter with inline command rendering
    const parts = content.split(/(\/[a-zA-Z0-9_-]+)/g);
    return (
      <div className="whitespace-pre-wrap">
        {parts.map((part, i) => {
          if (part.startsWith('/') && part.length > 2) {
            return (
              <button
                key={i}
                onClick={() => executeCommand(part)}
                className="font-mono text-[var(--accent)] hover:underline cursor-pointer bg-[var(--accent-soft)] px-2 py-0.5 rounded-md border border-[var(--accent-border)] font-bold text-xs"
              >
                {part}
              </button>
            );
          }
          return part;
        })}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full relative overflow-hidden bg-[var(--background)]">
      {/* Header */}
      <div className="h-16 px-5 border-b border-[var(--border)] bg-[var(--surface)] flex justify-between items-center shrink-0">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Cpu className="w-4 h-4 text-[var(--accent)]" />
            FDE System RAG Workspace
          </h2>
          <p className="text-xs text-[var(--subtle)] truncate font-mono">Session ID: {threadId.slice(0, 8)}</p>
        </div>
        <div className="flex items-center gap-3">
          <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" accept=".pdf,.docx,.txt" />
          <button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="btn btn-secondary px-3 py-2 text-sm">
            {uploading ? <Loader className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Upload doc
          </button>
        </div>
      </div>

      {/* Uploaded documents banner */}
      {uploadedDocs.length > 0 && (
        <div className="px-5 py-2 bg-[var(--surface-alt)] border-b border-[var(--border)] flex items-center gap-3 overflow-x-auto scrollbar-none shrink-0">
          <span className="text-[10px] uppercase font-bold tracking-wider text-[var(--muted)] shrink-0">Grounding Docs:</span>
          <div className="flex items-center gap-2">
            {uploadedDocs.map((doc: any) => (
              <div key={doc.id} className="px-2.5 py-1 bg-slate-900/60 border border-slate-800 text-[var(--foreground)] text-[10px] rounded-lg font-medium flex items-center gap-1.5 shadow-sm">
                <span className="max-w-[150px] truncate">{doc.filename}</span>
                <span className="text-[8px] text-[var(--muted)] font-mono">({((doc.size_bytes || doc.file_size || 1024) / 1024).toFixed(1)} KB)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload notice */}
      {uploadNotice && (
        <div className="absolute top-20 right-4 bg-[var(--success-soft)] border border-[var(--success-border)] text-[var(--success)] px-4 py-3 rounded-xl text-sm flex items-center gap-2 z-20 animate-fade-in shadow-md">
          <Check className="w-4 h-4" />
          <span>{uploadNotice}</span>
        </div>
      )}

      {/* Progress Modal */}
      {showProgressModal && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-[var(--border)] w-full max-w-lg shadow-2xl p-6 flex flex-col gap-5 animate-fade-in">
            <div className="flex justify-between items-center pb-3 border-b border-[var(--border)]">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-[var(--accent-soft)] rounded-xl border border-[var(--accent-border)]">
                  <BookOpen className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <div>
                  <h3 className="font-bold text-base">Course Progress Tracker</h3>
                  <p className="text-xs text-[var(--muted)]">Build your own multi-tenant personalized recommender system</p>
                </div>
              </div>
              <button 
                onClick={() => setShowProgressModal(false)}
                className="p-1.5 hover:bg-slate-100 rounded-lg text-[var(--muted)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {loadingProgress ? (
              <div className="flex flex-col items-center justify-center py-12 gap-2 text-[var(--muted)]">
                <Loader className="w-6 h-6 animate-spin text-[var(--accent)]" />
                <span className="text-xs font-medium">Fetching progress metrics...</span>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {courseProgress && (
                  <>
                    <div className="flex justify-between items-center text-sm font-semibold bg-slate-50 p-3 rounded-xl border border-slate-100">
                      <span>Curriculum Completion:</span>
                      <span className="text-[var(--accent)] text-base font-bold">
                        {((courseProgress.completed_chapters?.length || 0) / 9 * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1">
                      {[
                        "Introduction (Feedback Signals)",
                        "Collaborative Filtering (Cosine Engine)",
                        "Content-Based Personalization",
                        "Weighted Hybrid Recommendation Mixes",
                        "Knowledge-Based Rules vs Warm Start",
                        "System Evaluations (RMSE metrics)",
                        "Neural Networks & Sequences",
                        "Candidate Generation & ANN indexes",
                        "Capstone Multi-Tenant pipeline"
                      ].map((title, idx) => {
                        const chNum = idx + 1;
                        const isCompleted = courseProgress.completed_chapters?.includes(chNum);
                        return (
                          <div key={idx} className="flex justify-between items-center py-2 px-3 hover:bg-slate-50/50 rounded-lg border border-transparent transition">
                            <span className="text-xs font-semibold text-[var(--foreground)] flex gap-2">
                              <span className="text-[var(--muted)] font-mono">{chNum}.</span>
                              {title}
                            </span>
                            {isCompleted ? (
                              <span className="text-[var(--success)] flex items-center gap-1 text-[10px] font-bold bg-[var(--success-soft)] px-2 py-0.5 rounded-full border border-[var(--success-border)]">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Completed
                              </span>
                            ) : (
                              <span className="text-[var(--subtle)] text-[10px] font-semibold bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
                                Incomplete
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            )}
            
            <div className="flex justify-end pt-3 border-t border-[var(--border)]">
              <button 
                onClick={() => setShowProgressModal(false)}
                className="btn btn-secondary px-5 py-2.5 text-xs text-[var(--foreground)]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-5">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-5 max-w-md mx-auto py-12">
            <div className="p-4 bg-[var(--accent-soft)] border border-[var(--accent-border)] rounded-2xl shadow-sm">
              <BrainCircuit className="w-10 h-10 text-[var(--accent)] animate-pulse" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-[var(--foreground)]">FDE System RAG Workspace</h3>
              <p className="text-sm text-[var(--muted)] mt-2 leading-relaxed">
                Upload documents to ground your session, or ask questions against the hybrid BM25 + pgvector store. Type <code className="bg-slate-100 text-xs px-1.5 py-0.5 rounded font-mono font-semibold">/</code> to trigger slash commands.
              </p>
            </div>
            <div className="flex flex-wrap gap-2.5 justify-center">
              <button 
                onClick={() => executeCommand('/hybrid-search')}
                className="btn btn-secondary px-4 py-2.5 text-xs font-bold text-[var(--accent)] bg-[var(--accent-soft)] border-[var(--accent-border)]"
              >
                Hybrid Search
              </button>
              <button 
                onClick={() => executeCommand('/agent-state')}
                className="btn btn-secondary px-4 py-2.5 text-xs font-semibold text-[var(--muted)]"
              >
                Inspect Agent State
              </button>
            </div>
          </div>
        )}

        {messages.map((m, idx) => {
          if (m.role === 'system') {
            return (
              <div key={idx} className="self-center px-4 py-1.5 rounded-full bg-amber-50 text-amber-700 text-xs border border-amber-200/60 shadow-sm font-semibold my-1 animate-fade-in">
                {m.content}
              </div>
            );
          }
          const suggestions = getSuggestions(m.content);
          return (
            <div key={idx} className={`flex gap-3 max-w-2xl ${m.role === 'human' ? 'self-end flex-row-reverse' : 'self-start'}`}>
              <div
                className={`p-2 rounded-lg shrink-0 flex items-center justify-center h-fit border ${
                  m.role === 'human'
                    ? 'bg-[var(--accent)] border-transparent'
                    : 'bg-[var(--surface)] border-[var(--border)]'
                }`}
              >
                {m.role === 'human' ? <User className="w-4 h-4 text-white" /> : <Cpu className="w-4 h-4 text-[var(--accent)]" />}
              </div>
              <div className="flex flex-col gap-2">
                <div
                  className={`px-4 py-3 rounded-2xl text-sm leading-relaxed border ${
                    m.role === 'human'
                      ? 'bg-[var(--accent)] text-white border-transparent rounded-tr-sm shadow-sm'
                      : 'bg-[var(--surface)] text-[var(--foreground)] border-[var(--border)] rounded-tl-sm shadow-sm'
                  }`}
                >
                  {m.role === 'human' ? (
                    <div className="whitespace-pre-wrap font-medium">{m.content}</div>
                  ) : (
                    renderMessageContent(m.content)
                  )}
                </div>
                
                {/* Suggestions Chips below the message */}
                {m.role === 'ai' && suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2 items-center pl-1 mt-0.5">
                    <span className="text-[10px] font-bold text-[var(--muted)] uppercase tracking-wider">Suggested action:</span>
                    {suggestions.map((cmd) => (
                      <button
                        key={cmd}
                        onClick={() => executeCommand(cmd)}
                        className="btn btn-secondary text-[10px] font-bold px-2.5 py-1 text-[var(--accent)] bg-[var(--accent-soft)] border-[var(--accent-border)] hover:bg-[var(--accent-border)] cursor-pointer"
                      >
                        Run {cmd}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Tool log */}
        {toolLogs.length > 0 && (
          <div className="card p-4 flex flex-col gap-1.5 max-w-2xl self-start font-mono text-xs text-[var(--muted)] bg-slate-900 border-slate-950 text-slate-100">
            <div className="flex items-center gap-2 pb-1.5 mb-1 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
              <Terminal className="w-3.5 h-3.5 text-[var(--accent)]" /> Tool activity
            </div>
            {toolLogs.map((log, idx) => (
              <div key={idx}>{log}</div>
            ))}
          </div>
        )}

        {/* Streaming reply */}
        {streamingContent && (
          <div className="flex gap-3 max-w-2xl self-start">
            <div className="p-2 rounded-lg shrink-0 flex items-center justify-center bg-[var(--surface)] border border-[var(--border)] h-fit">
              <Cpu className="w-4 h-4 text-[var(--accent)] animate-pulse" />
            </div>
            <div className="px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed bg-[var(--surface)] border border-[var(--border)] shadow-sm">
              {renderMessageContent(streamingContent)}
              <span className="inline-block w-1.5 h-4 bg-[var(--accent)] ml-0.5 align-middle animate-blink" />
            </div>
          </div>
        )}

        {/* Active HITL Interrupt Confirmation Card */}
        {activeInterrupt && (
          <div className="flex gap-3 max-w-2xl self-start w-full animate-fade-in">
            <div className="p-2 rounded-lg shrink-0 flex items-center justify-center bg-white border border-amber-200 h-fit shadow-sm">
              <BrainCircuit className="w-4 h-4 text-amber-500 animate-pulse" />
            </div>
            <div className="flex-1 px-5 py-4 rounded-2xl rounded-tl-sm border border-amber-200 bg-amber-50/40 backdrop-blur-md shadow-md flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-amber-700 uppercase tracking-wider">Human-in-the-Loop Confirmation Required</span>
              </div>
              <p className="text-sm text-slate-800 font-semibold leading-relaxed">
                {activeInterrupt.warning || 'A destructive action is requested. Please confirm if you wish to proceed.'}
              </p>
              <div className="flex gap-2.5 mt-1">
                <button
                  onClick={() => handleInterruptResponse(true)}
                  disabled={loading}
                  className="btn btn-primary px-4 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl transition cursor-pointer border border-transparent shadow-sm"
                >
                  Yes, Wipe Data
                </button>
                <button
                  onClick={() => handleInterruptResponse(false)}
                  disabled={loading}
                  className="btn btn-secondary px-4 py-2 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 rounded-xl transition cursor-pointer border border-slate-200 shadow-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input section with Autocomplete */}
      <div className="p-4 border-t border-[var(--border)] bg-[var(--surface)] shrink-0 relative">
        {/* Floating Autocomplete Dropdown */}
        {showAutocomplete && filteredCommands.length > 0 && (
          <div className="absolute bottom-[4.5rem] left-4 right-4 bg-white border border-[var(--border)] rounded-2xl shadow-xl z-30 max-h-56 overflow-y-auto p-2 flex flex-col gap-0.5 animate-fade-in">
            <div className="px-3 py-1.5 text-[9px] uppercase font-bold tracking-wider text-[var(--muted)] border-b border-slate-100 mb-1">
              Curriculum Slash Commands
            </div>
            {filteredCommands.map((cmd) => (
              <button
                key={cmd.name}
                type="button"
                onClick={() => {
                  setInput(cmd.name);
                  setShowAutocomplete(false);
                }}
                className="w-full text-left px-3 py-2 rounded-xl hover:bg-[var(--accent-soft)] flex justify-between items-center text-xs transition cursor-pointer"
              >
                <span className="font-mono font-bold text-[var(--accent)]">{cmd.name}</span>
                <span className="text-[10px] text-[var(--muted)] font-medium truncate max-w-[250px]">{cmd.desc}</span>
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleSend} className="max-w-3xl mx-auto flex gap-2.5">
          <input
            type="text"
            required
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            disabled={loading}
            placeholder="Type a message or slash command..."
            className="input flex-1 py-3 px-4 rounded-xl text-sm border-[var(--border)] bg-[var(--background)] focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] outline-none"
          />
          <button type="submit" disabled={loading} className="btn btn-primary px-5 py-3 rounded-xl bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition cursor-pointer shadow-md">
            {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </button>
        </form>
      </div>
    </div>
  );
}
