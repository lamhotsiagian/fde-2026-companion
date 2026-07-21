export interface User {
  id: string;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
}

export interface Thread {
  id: string;
  title: string;
  user_id: string;
  created_at: string;
}

export interface Memory {
  id: string;
  user_id: string;
  thread_id?: string;
  memory_type: 'episodic' | 'semantic' | 'procedural' | 'entity';
  content: string;
  importance_score: number;
  access_count: number;
  last_accessed_at: string;
  created_at: string;
  decay_rate: number;
  is_active: boolean;
  is_shared: boolean;
  metadata_json: string;
}

export interface Message {
  role: 'human' | 'ai' | 'system' | 'tool';
  content: string;
}

export interface MemoryConflict {
  id: string;
  user_id: string;
  memory_id_old: string;
  memory_id_new: string;
  old_content: string;
  new_content: string;
  conflict_type: string;
  resolution?: string;
  is_resolved: boolean;
  created_at: string;
}

export interface MemoryStats {
  total_count: number;
  counts_by_type: Record<string, number>;
  avg_importance: number;
  active_count: number;
  inactive_count: number;
}
