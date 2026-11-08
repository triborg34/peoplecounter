import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios';

// API base URL - points to the FastAPI backend
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (token: string) => void;
    reject: (error: Error) => void;
  }> = [];

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    this.setupInterceptors();
    this.loadTokens();
  }

  private loadTokens() {
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  private saveTokens(access: string, refresh: string) {
    this.accessToken = access;
    this.refreshToken = refresh;
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }

  private clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  private setupInterceptors() {
    // Request interceptor - add auth header
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (this.accessToken && config.headers) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
          if (this.isRefreshing) {
            // Queue the request
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then((token) => {
                originalRequest.headers!.Authorization = `Bearer ${token}`;
                return this.client(originalRequest);
              })
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
              refresh_token: this.refreshToken,
            });

            const { access_token, refresh_token } = response.data;
            this.saveTokens(access_token, refresh_token);

            this.processQueue(null, access_token);
            originalRequest.headers!.Authorization = `Bearer ${access_token}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            this.processQueue(refreshError as Error, '');
            this.clearTokens();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(error);
      }
    );
  }

  private processQueue(error: Error | null, token: string) {
    this.failedQueue.forEach(({ resolve, reject }) => {
      if (error) {
        reject(error);
      } else {
        resolve(token);
      }
    });
    this.failedQueue = [];
  }

  // Auth methods
  async login(username: string, password: string) {
    const response = await this.client.post('/auth/login', { username, password });
    const { access_token, refresh_token, user } = response.data;
    this.saveTokens(access_token, refresh_token);
    return { user, access_token, refresh_token };
  }

  async logout() {
    try {
      await this.client.post('/auth/logout');
    } finally {
      this.clearTokens();
    }
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  async changePassword(currentPassword: string, newPassword: string) {
    const response = await this.client.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  }

  // Camera methods
  async getCameras(params?: { page?: number; size?: number; search?: string }) {
    const response = await this.client.get('/cameras', { params });
    return response.data;
  }

  async getCamera(id: number) {
    const response = await this.client.get(`/cameras/${id}`);
    return response.data;
  }

  async createCamera(data: any) {
    const response = await this.client.post('/cameras', data);
    return response.data;
  }

  async updateCamera(id: number, data: any) {
    const response = await this.client.put(`/cameras/${id}`, data);
    return response.data;
  }

  async deleteCamera(id: number) {
    const response = await this.client.delete(`/cameras/${id}`);
    return response.data;
  }

  async getCameraStreamUrl(id: number) {
    const response = await this.client.get(`/cameras/${id}/stream`);
    return response.data;
  }

  async getCameraSnapshot(id: number) {
    const response = await this.client.get(`/cameras/${id}/snapshot`, {
      responseType: 'blob',
    });
    return URL.createObjectURL(response.data);
  }

  async toggleCamera(id: number, enabled: boolean) {
    const response = await this.client.patch(`/cameras/${id}/toggle`, { enabled });
    return response.data;
  }

  // Zone methods
  async getZones(cameraId: number) {
    const response = await this.client.get(`/cameras/${cameraId}/zones`);
    return response.data;
  }

  async createZone(cameraId: number, data: any) {
    const response = await this.client.post(`/cameras/${cameraId}/zones`, data);
    return response.data;
  }

  async updateZone(cameraId: number, zoneId: number, data: any) {
    const response = await this.client.put(`/cameras/${cameraId}/zones/${zoneId}`, data);
    return response.data;
  }

  async deleteZone(cameraId: number, zoneId: number) {
    const response = await this.client.delete(`/cameras/${cameraId}/zones/${zoneId}`);
    return response.data;
  }

  // Count methods
  async getCounts(params?: {
    camera_id?: number;
    zone_id?: number;
    start_time?: string;
    end_time?: string;
    page?: number;
    size?: number;
  }) {
    const response = await this.client.get('/counts', { params });
    return response.data;
  }

  async getCountStats(params?: {
    camera_id?: number;
    zone_id?: number;
    start_time?: string;
    end_time?: string;
    interval?: string;
  }) {
    const response = await this.client.get('/counts/stats', { params });
    return response.data;
  }

  async getLiveCounts() {
    const response = await this.client.get('/counts/live');
    return response.data;
  }

  // Report methods
  async getReports(params?: {
    camera_id?: number;
    zone_id?: number;
    start_date?: string;
    end_date?: string;
    page?: number;
    size?: number;
  }) {
    const response = await this.client.get('/reports', { params });
    return response.data;
  }

  async generateReport(data: {
    camera_id?: number;
    zone_id?: number;
    start_date: string;
    end_date: string;
    format: 'pdf' | 'excel';
  }) {
    const response = await this.client.post('/reports/generate', data, {
      responseType: 'blob',
    });
    return response.data;
  }

  async getReportStats(params?: {
    camera_id?: number;
    zone_id?: number;
    start_date?: string;
    end_date?: string;
  }) {
    const response = await this.client.get('/reports/stats', { params });
    return response.data;
  }

  // User methods (admin only)
  async getUsers(params?: { page?: number; size?: number; search?: string }) {
    const response = await this.client.get('/users', { params });
    return response.data;
  }

  async getUser(id: number) {
    const response = await this.client.get(`/users/${id}`);
    return response.data;
  }

  async createUser(data: any) {
    const response = await this.client.post('/users', data);
    return response.data;
  }

  async updateUser(id: number, data: any) {
    const response = await this.client.put(`/users/${id}`, data);
    return response.data;
  }

  async deleteUser(id: number) {
    const response = await this.client.delete(`/users/${id}`);
    return response.data;
  }

  async toggleUserStatus(id: number, isActive: boolean) {
    const response = await this.client.patch(`/users/${id}/toggle`, { is_active: isActive });
    return response.data;
  }

  // Settings methods
  async getSettings() {
    const response = await this.client.get('/settings');
    return response.data;
  }

  async updateSettings(data: any) {
    const response = await this.client.put('/settings', data);
    return response.data;
  }

  // WebSocket connection for live updates
  createWebSocket(path: string): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '').replace(/\/api\/v1/, '');
    const ws = new WebSocket(`${protocol}//${host}/ws${path}`);
    return ws;
  }

  // Token getters
  getAccessToken(): string | null {
    return this.accessToken;
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }
}

export const api = new ApiClient();
export default api;