import client from './client';
import type { Collection, CollectionCreate } from '@/types';

interface CollectionListResponse {
  total: number;
  items: Collection[];
}

export const collectionsApi = {
  list: async (params?: { skip?: number; limit?: number; status?: string }) => {
    const response = await client.get<CollectionListResponse>('/api/v1/collections', { params });
    return response.data.items; // 返回items数组
  },

  get: async (id: string) => {
    const response = await client.get<Collection>(`/api/v1/collections/${id}`);
    return response.data;
  },

  create: async (data: CollectionCreate) => {
    const response = await client.post<Collection>('/api/v1/collections', data);
    return response.data;
  },

  update: async (id: string, data: Partial<Collection>) => {
    const response = await client.put<Collection>(`/api/v1/collections/${id}`, data);
    return response.data;
  },

  delete: async (id: string) => {
    const response = await client.delete(`/api/v1/collections/${id}`);
    return response.data;
  },

  archive: async (id: string) => {
    const response = await client.post(`/api/v1/collections/${id}/archive`);
    return response.data;
  },

  statistics: async (id: string) => {
    const response = await client.get(`/api/v1/collections/${id}/statistics`);
    return response.data;
  },
};

