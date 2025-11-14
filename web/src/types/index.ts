// User types
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
}

// Collection types
export interface Collection {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  icon_url?: string;
  status: 'active' | 'archived';
  document_count: number;
  chunk_count: number;
  total_size_bytes: number;
  created_at: string;
  updated_at: string;
  last_updated_at?: string;
}

export interface CollectionCreate {
  name: string;
  description?: string;
  icon_url?: string;
  settings?: {
    chunking_strategy?: {
      strategy_type: 'fixed' | 'paragraph' | 'semantic';
      config: Record<string, any>;
    };
  };
}

// Document types
export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

// Search types
export interface SearchRequest {
  query: string;
  collection_ids: string[];
  mode: 'vector' | 'fulltext' | 'hybrid';
  top_k?: number;
  threshold?: number;
  vector_weight?: number;
  fulltext_weight?: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_name: string;
  collection_id: string;
  collection_name: string;
  content: string;
  score: number;
  metadata?: Record<string, any>;
}

// Share types
export interface CollectionShare {
  id: string;
  share_token: string;
  collection_id: string;
  collection_name?: string;
  is_enabled: boolean;
  expires_at?: string;
  usage_count: number;
  last_used_at?: string;
  created_at: string;
}

