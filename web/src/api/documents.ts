import client from './client';
import type { Document } from '@/types';

interface DocumentListResponse {
  total: number;
  items: Document[];
}

export const documentsApi = {
  list: async (collectionId: string, params?: { limit?: number; offset?: number; status_filter?: string }) => {
    const response = await client.get<DocumentListResponse>(`/api/v1/collections/${collectionId}/documents`, { params });
    return response.data.items; // 返回items数组
  },

  get: async (id: string) => {
    const response = await client.get<Document>(`/api/v1/documents/${id}`);
    return response.data;
  },

  upload: async (collectionId: string, files: FormData) => {
    const response = await client.post(`/api/v1/collections/${collectionId}/documents/upload`, files, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  delete: async (documentIds: string[]) => {
    const response = await client.delete('/api/v1/documents', { data: { document_ids: documentIds } });
    return response.data;
  },

  process: async (documentIds: string[]) => {
    const response = await client.post('/api/v1/documents/process', { document_ids: documentIds });
    return response.data;
  },

  reprocess: async (id: string) => {
    const response = await client.post(`/api/v1/documents/${id}/reprocess`);
    return response.data;
  },

  getStatus: async (id: string) => {
    const response = await client.get(`/api/v1/documents/${id}/status`);
    return response.data;
  },

  getChunks: async (id: string) => {
    const response = await client.get(`/api/v1/documents/${id}/chunks`);
    return response.data;
  },
};

