// Types mirroring the FastAPI backend schemas (app/api/v1/schemas.py).

export interface User {
  id: number;
  username: string;
  email: string | null;
  full_name: string;
  role: 'admin' | 'operator' | 'viewer';
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Camera {
  id: number;
  name: string;
  location: string;
  source_type: 'rtsp' | 'file';
  enabled: boolean;
  host: string | null;
  port: number | null;
  username: string | null;
  has_password: boolean;
  rtsp_path: string;
  rtsp_url: string | null;
  file_path: string | null;
  fps_limit: number;
  detection_enabled: boolean;
  use_gpu: boolean;
  color: string;
  status: string;
  live_fps: number;
  last_error: string;
}

export interface CameraCreate {
  name: string;
  location?: string;
  mode?: 'manual' | 'url' | 'file';
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  rtsp_path?: string;
  url?: string;
  file_path?: string;
  fps_limit?: number;
  detection_enabled?: boolean;
  enabled?: boolean;
}

export type CameraUpdate = Partial<CameraCreate>;

export interface CameraStatus {
  camera_id: number;
  name: string;
  status: string;
  fps: number;
  last_error: string;
  reconnect_attempts: number;
  detection_enabled: boolean;
}

export interface TestConnectionResult {
  ok: boolean;
  message: string;
  width: number;
  height: number;
  fps: number;
}

// Zones are split into lines and areas on the backend.
/** What each crossing of the line counts as.
 *  Two slots, "<A->B><B->A>": I = IN, O = OUT, X = ignored. */
export type LineDirection = string;

export interface Line {
  id: number;
  camera_id: number;
  name: string;
  color: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  direction: LineDirection;
  enabled: boolean;
}

export interface LineCreate {
  name: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  direction?: LineDirection;
  color?: string;
  enabled?: boolean;
}

export interface Area {
  id: number;
  camera_id: number;
  name: string;
  color: string;
  points: number[][];
  enabled: boolean;
}

export interface AreaCreate {
  name: string;
  points: number[][];
  color?: string;
  enabled?: boolean;
}

export interface CountsOut {
  camera_id: number | null;
  summary: Record<string, number>;
  lines: Record<string, Record<string, unknown>>;
  areas: Record<string, Record<string, unknown>>;
  occupancy: Record<string, number>;
}

export interface GlobalCountsOut {
  summary: Record<string, number>;
  per_camera: Array<Record<string, unknown>>;
}

export interface CountEvent {
  id: number;
  timestamp: string;
  camera_id: number;
  camera_name: string;
  kind: string;
  target_id: number | null;
  target_name: string;
  direction: string;
  track_id: number;
  confidence: number;
}

export interface CountStats {
  total_in: number;
  total_out: number;
  net_count: number;
  by_camera: Record<string, { in: number; out: number; net: number }>;
  by_zone: Record<string, { in: number; out: number; net: number }>;
  timeline: Array<Record<string, unknown>>;
}

export interface LiveCount {
  camera_id: number;
  camera_name: string;
  zone_id: number | null;
  zone_name: string | null;
  current_count: number;
  total_in: number;
  total_out: number;
  last_event: CountEvent | null;
}

export interface ReportSummary {
  filters: Record<string, unknown>;
  totals: Record<string, number>;
  timeseries: Array<Record<string, unknown>>;
  by_camera: Array<Record<string, unknown>>;
  by_target: Array<Record<string, unknown>>;
  peak_hours: Array<Record<string, unknown>>;
  events: Array<Record<string, unknown>>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  username: string;
  action: string;
  entity_type: string;
  entity_id: number | null;
  details: string;
}
