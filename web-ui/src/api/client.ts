import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type {
  Camera,
  CameraCreate,
  CameraUpdate,
  Line,
  LineCreate,
  Area,
  AreaCreate,
  User,
  PaginatedResponse,
  ReportSummary,
  CountStats,
  LiveCount,
  GlobalCountsOut,
} from './types';

// Relative by default: the Vite dev server proxies /api to the backend and
// in production the app is served from the same origin as the API.
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/** Absolute origin of the API, for <img>/<video> sources and WebSockets. */
function apiOrigin(): string {
  if (/^https?:\/\//.test(API_BASE_URL)) {
    return API_BASE_URL.replace(/\/api\/v1\/?$/, '');
  }
  return window.location.origin;
}

// The backend list endpoints return plain arrays. Wrap them in a
// paginated envelope so pages can keep using `.items` / `.total`.
function paginate<T>(items: T[], page = 1, size = 20): PaginatedResponse<T> {
  const total = items.length;
  return {
    items,
    total,
    page,
    size,
    pages: Math.max(1, Math.ceil(total / size)),
  };
}

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
      headers: { 'Content-Type': 'application/json' },
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
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (this.accessToken && config.headers) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
          if (this.isRefreshing) {
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
            // The refresh endpoint expects { refresh_token } and returns a full TokenResponse.
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
      if (error) reject(error);
      else resolve(token);
    });
    this.failedQueue = [];
  }

  // ---- Auth ----------------------------------------------------------
  async login(username: string, password: string) {
    const response = await this.client.post('/auth/login', { username, password });
    const { access_token, refresh_token, user } = response.data;
    this.saveTokens(access_token, refresh_token);
    return { user: user as User, access_token, refresh_token };
  }

  async logout() {
    // The backend has no logout endpoint (JWTs are stateless); just drop tokens.
    this.clearTokens();
  }

  async getCurrentUser(): Promise<User> {
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

  // ---- Cameras -------------------------------------------------------
  async getCameras(params?: { page?: number; size?: number; search?: string }) {
    const response = await this.client.get<Camera[]>('/cameras');
    let items = response.data;
    if (params?.search) {
      const q = params.search.toLowerCase();
      items = items.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.location || '').toLowerCase().includes(q) ||
          (c.host || '').toLowerCase().includes(q)
      );
    }
    return paginate(items, params?.page ?? 1, params?.size ?? 20);
  }

  async getCamera(id: number): Promise<Camera> {
    const response = await this.client.get(`/cameras/${id}`);
    return response.data;
  }

  async createCamera(data: CameraCreate): Promise<Camera> {
    const response = await this.client.post('/cameras', data);
    return response.data;
  }

  async updateCamera(id: number, data: CameraUpdate): Promise<Camera> {
    const response = await this.client.patch(`/cameras/${id}`, data);
    return response.data;
  }

  async deleteCamera(id: number) {
    await this.client.delete(`/cameras/${id}`);
  }

  async testCameraConnection(id: number) {
    const response = await this.client.post(`/cameras/${id}/test`);
    return response.data;
  }

  async getCameraStatus(id: number) {
    const response = await this.client.get(`/cameras/${id}/status`);
    return response.data;
  }

  /** MJPEG stream URL (needs the bearer token, so we return a URL with the token). */
  getCameraStreamUrl(id: number): string {
    const token = this.accessToken ? `?token=${encodeURIComponent(this.accessToken)}` : '';
    return `${apiOrigin()}/api/v1/cameras/${id}/stream${token}`;
  }

  async getCameraSnapshot(id: number): Promise<string> {
    const response = await this.client.get(`/cameras/${id}/snapshot`, { responseType: 'blob' });
    return URL.createObjectURL(response.data);
  }

  /** Direct snapshot URL usable in <img src>; auth travels as ?token=. */
  getCameraSnapshotUrl(id: number): string {
    const token = this.accessToken ? `?token=${encodeURIComponent(this.accessToken)}` : '';
    return `${apiOrigin()}/api/v1/cameras/${id}/snapshot${token}`;
  }

  async toggleCamera(id: number, enabled: boolean): Promise<Camera> {
    const response = await this.client.patch(`/cameras/${id}`, { enabled });
    return response.data;
  }

  // ---- Lines (counting lines) ---------------------------------------
  async getLines(cameraId: number): Promise<Line[]> {
    const response = await this.client.get(`/cameras/${cameraId}/lines`);
    return response.data;
  }

  async createLine(cameraId: number, data: LineCreate): Promise<Line> {
    const response = await this.client.post(`/cameras/${cameraId}/lines`, data);
    return response.data;
  }

  async updateLine(cameraId: number, lineId: number, data: Partial<LineCreate>): Promise<Line> {
    const response = await this.client.patch(`/cameras/${cameraId}/lines/${lineId}`, data);
    return response.data;
  }

  async deleteLine(cameraId: number, lineId: number) {
    await this.client.delete(`/cameras/${cameraId}/lines/${lineId}`);
  }

  // ---- Areas (counting areas) ---------------------------------------
  async getAreas(cameraId: number): Promise<Area[]> {
    const response = await this.client.get(`/cameras/${cameraId}/areas`);
    return response.data;
  }

  async createArea(cameraId: number, data: AreaCreate): Promise<Area> {
    const response = await this.client.post(`/cameras/${cameraId}/areas`, data);
    return response.data;
  }

  async updateArea(cameraId: number, areaId: number, data: Partial<AreaCreate>): Promise<Area> {
    const response = await this.client.patch(`/cameras/${cameraId}/areas/${areaId}`, data);
    return response.data;
  }

  async deleteArea(cameraId: number, areaId: number) {
    await this.client.delete(`/cameras/${cameraId}/areas/${areaId}`);
  }

  // ---- Counts --------------------------------------------------------
  async getCounts(): Promise<GlobalCountsOut> {
    const response = await this.client.get('/counts');
    return response.data;
  }

  async getCountStats(params?: {
    start?: string;
    end?: string;
    interval?: string;
    camera_id?: number;
  }): Promise<CountStats> {
    const response = await this.client.get('/counts/stats', { params });
    return response.data;
  }

  async getLiveCounts(): Promise<LiveCount[]> {
    const response = await this.client.get('/counts/live');
    return response.data;
  }

  async getCountEvents(params?: Record<string, unknown>) {
    const response = await this.client.get('/counts/events', { params });
    return response.data;
  }

  // ---- Reports -------------------------------------------------------
  async getReportSummary(params: {
    start?: string;
    end?: string;
    camera_id?: number[];
    kind?: string;
    target_id?: number;
    direction?: string;
    interval?: string;
  }): Promise<ReportSummary> {
    const response = await this.client.get('/reports/summary', {
      params,
      paramsSerializer: { indexes: null },
    });
    return response.data;
  }

  /** Download a CSV / Excel / PDF export as a Blob. */
  async exportReport(params: {
    format: 'csv' | 'excel' | 'pdf';
    start?: string;
    end?: string;
    camera_id?: number[];
    kind?: string;
    direction?: string;
  }): Promise<Blob> {
    const response = await this.client.get('/reports/export', {
      params,
      paramsSerializer: { indexes: null },
      responseType: 'blob',
    });
    return response.data;
  }

  // ---- Users ---------------------------------------------------------
  async getUsers(params?: { page?: number; size?: number; search?: string }) {
    const response = await this.client.get<User[]>('/users');
    let items = response.data;
    if (params?.search) {
      const q = params.search.toLowerCase();
      items = items.filter(
        (u) =>
          u.username.toLowerCase().includes(q) ||
          (u.full_name || '').toLowerCase().includes(q) ||
          (u.email || '').toLowerCase().includes(q)
      );
    }
    return paginate(items, params?.page ?? 1, params?.size ?? 20);
  }

  async getUser(id: number): Promise<User> {
    const response = await this.client.get(`/users/${id}`);
    return response.data;
  }

  async createUser(data: {
    username: string;
    password: string;
    full_name?: string;
    email?: string;
    role?: string;
  }): Promise<User> {
    const response = await this.client.post('/users', data);
    return response.data;
  }

  async updateUser(id: number, data: Partial<User> & { password?: string }): Promise<User> {
    const response = await this.client.patch(`/users/${id}`, data);
    return response.data;
  }

  async deleteUser(id: number) {
    await this.client.delete(`/users/${id}`);
  }

  async toggleUserStatus(id: number, isActive: boolean): Promise<User> {
    const response = await this.client.patch(`/users/${id}`, { is_active: isActive });
    return response.data;
  }

  async getAuditLog(params?: { limit?: number }) {
    const response = await this.client.get('/users/audit', { params });
    return response.data;
  }

  /** Public health/system status (no auth required). */
  async getSystemStatus() {
    const response = await axios.get(`${apiOrigin()}/health`);
    return response.data;
  }

  // ---- WebSocket -----------------------------------------------------
  createWebSocket(path: string): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = apiOrigin().replace(/^https?:\/\//, '');
    const token = this.accessToken ? `?token=${encodeURIComponent(this.accessToken)}` : '';
    return new WebSocket(`${protocol}//${host}/api/v1${path}${token}`);
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }
}

export const api = new ApiClient();
export default api;
