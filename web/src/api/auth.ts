import client from './client';
import type { User } from '@/types';

interface LoginRequest {
  username: string;
  password: string;
}

interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    // 后端期望 username_or_email 字段
    const response = await client.post<TokenResponse>('/api/v1/auth/login', {
      username_or_email: data.username,
      password: data.password,
    });
    // 获取token后，立即获取用户信息
    const token = response.data.access_token;
    const userResponse = await client.get<User>('/api/v1/users/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return {
      access_token: token,
      token_type: response.data.token_type,
      user: userResponse.data,
    };
  },

  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await client.post<TokenResponse>('/api/v1/auth/register', data);
    // 获取token后，立即获取用户信息
    const token = response.data.access_token;
    const userResponse = await client.get<User>('/api/v1/users/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return {
      access_token: token,
      token_type: response.data.token_type,
      user: userResponse.data,
    };
  },

  me: async () => {
    const response = await client.get<User>('/api/v1/users/me');
    return response.data;
  },

  updateProfile: async (data: Partial<User>) => {
    const response = await client.put<User>('/api/v1/auth/me', data);
    return response.data;
  },
};

