import client from './client';
import type { CollectionShare, SearchRequest, SearchResult } from '@/types';

interface CreateShareRequest {
  expires_at?: string;
  search_config?: {
    top_k?: number;
    threshold?: number;
    allowed_modes?: string[];
  };
}

export const sharesApi = {
  create: async (collectionId: string, data?: CreateShareRequest) => {
    const response = await client.post<CollectionShare>(`/api/v1/collections/${collectionId}/share`, data);
    return response.data;
  },

  list: async () => {
    const response = await client.get<CollectionShare[]>('/api/v1/shares');
    return response.data;
  },

  get: async (shareToken: string) => {
    const response = await client.get<CollectionShare>(`/api/v1/shares/${shareToken}`);
    return response.data;
  },

  update: async (shareId: string, data: Partial<CreateShareRequest>) => {
    const response = await client.put<CollectionShare>(`/api/v1/shares/${shareId}`, data);
    return response.data;
  },

  delete: async (shareId: string) => {
    const response = await client.delete(`/api/v1/shares/${shareId}`);
    return response.data;
  },

  search: async (shareToken: string, params: Omit<SearchRequest, 'collection_ids'>) => {
    const response = await client.post<SearchResult[]>(`/api/v1/shares/${shareToken}/search`, params);
    return response.data;
  },
};

