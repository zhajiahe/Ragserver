import client from './client';
import type { SearchRequest, SearchResult } from '@/types';

export const searchApi = {
  search: async (params: SearchRequest) => {
    const response = await client.post<SearchResult[]>('/api/v1/search', params);
    return response.data;
  },
};

