const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options;
    
    let url = `${this.baseUrl}${endpoint}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const response = await fetch(url, {
      ...fetchOptions,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...fetchOptions.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: "An error occurred" }));
      throw new Error(error.message || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async get<T>(endpoint: string, params?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, { method: "GET", params });
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" });
  }
}

export const api = new ApiClient(API_BASE);

// Auth API
export const authApi = {
  login: () => `${API_BASE}/api/v1/auth/login`,
  logout: () => api.post("/api/v1/auth/logout"),
  me: () => api.get<User>("/api/v1/auth/me"),
};

// Products API
export const productsApi = {
  list: (params?: { guild_id?: number; user_id?: number }) =>
    api.get<Product[]>("/api/v1/products/", params as Record<string, string>),
  get: (productId: string) => api.get<Product>(`/api/v1/products/${productId}`),
  create: (data: CreateProduct) => api.post<Product>("/api/v1/products/", data),
  update: (productId: string, data: UpdateProduct) =>
    api.put<Product>(`/api/v1/products/${productId}`, data),
  delete: (productId: string) => api.delete(`/api/v1/products/${productId}`),
  history: (productId: string) =>
    api.get<PriceHistory[]>(`/api/v1/products/${productId}/history`),
};

// Guilds API
export const guildsApi = {
  list: () => api.get<Guild[]>("/api/v1/guilds/"),
  get: (discordId: string) => api.get<Guild>(`/api/v1/guilds/${discordId}`),
};

// Types
export interface User {
  id: number;
  discord_id: string;
  username: string;
  avatar_url: string;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: number;
  product_id: string;
  name: string;
  url: string;
  image_url: string;
  current_price: number;
  original_price: number;
  last_checked: string;
  created_at: string;
  user_id: number;
  guild_id: number;
  channel_id: string;
  username: string;
  avatar_url: string;
}

export interface CreateProduct {
  product_id: string;
  name: string;
  url: string;
  image_url?: string;
  current_price?: number;
  original_price?: number;
  guild_id: number;
  channel_id?: string;
}

export interface UpdateProduct {
  name?: string;
  url?: string;
  image_url?: string;
  current_price?: number;
  original_price?: number;
}

export interface PriceHistory {
  id: number;
  price: number;
  timestamp: string;
}

export interface Guild {
  id: number;
  discord_id: string;
  name: string;
  icon_url: string;
  owner_id: string;
  created_at: string;
  product_count: number;
}
