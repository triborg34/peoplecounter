export interface User {
  id: number;
  username: string;
  email: string | null;
  full_name: string | null;
  role: 'admin' | 'operator' | 'viewer';
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

export interface Camera {
  id: number;
  name: string;
  location: string | null;
  source_type: 'rtsp' | 'http' | 'file' | 'usb';
  source_url: string;
  enabled: boolean;
  username: string | null;
  password: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  detection_enabled: boolean;
  detection_confidence: number;
  detection_classes: number[] | null;
  zone_count: number;
  created_at: string;
  updated_at: string;
  status?: 'online' | 'offline' | 'error';
  last_frame_at?: string | null;
}

export interface CameraCreate {
  name: string;
  location?: string;
  source_type: 'rtsp' | 'http' | 'file' | 'usb';
  source_url: string;
  enabled?: boolean;
  username?: string;
  password?: string;
  width?: number;
  height?: number;
  fps?: number;
  detection_enabled?: boolean;
  detection_confidence?: number;
  detection_classes?: number[];
}

export interface CameraUpdate extends Partial<CameraCreate> {}

export interface Zone {
  id: number;
  camera_id: number;
  name: string;
  zone_type: 'line' | 'area';
  coordinates: number[][];
  direction: 'in' | 'out' | 'both';
  color: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ZoneCreate {
  name: string;
  zone_type: 'line' | 'area';
  coordinates: number[][];
  direction?: 'in' | 'out' | 'both';
  color?: string;
  enabled?: boolean;
}

export interface ZoneUpdate extends Partial<ZoneCreate> {}

export interface CountEvent {
  id: number;
  camera_id: number;
  camera_name: string;
  zone_id: number | null;
  zone_name: string | null;
  track_id: number;
  direction: 'in' | 'out';
  timestamp: string;
  confidence: number;
  bbox: number[];
}

export interface CountStats {
  total_in: number;
  total_out: number;
  net_count: number;
  by_camera: Record<string, { in: number; out: number; net: number }>;
  by_zone: Record<string, { in: number; out: number; net: number }>;
  timeline: Array<{
    timestamp: string;
    in: number;
    out: number;
  }>;
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

export interface Report {
  id: number;
  name: string;
  camera_id: number | null;
  zone_id: number | null;
  start_date: string;
  end_date: string;
  format: 'pdf' | 'excel';
  file_path: string;
  file_size: number;
  generated_at: string;
  generated_by: number;
}

export interface ReportGenerate {
  camera_id?: number;
  zone_id?: number;
  start_date: string;
  end_date: string;
  format: 'pdf' | 'excel';
}

export interface ReportStats {
  total_reports: number;
  total_size: number;
  by_format: Record<string, number>;
  recent_reports: Report[];
}

export interface Settings {
  app_name: string;
  api_enabled: boolean;
  api_host: string;
  api_port: number;
  cors_origins: string[];
  log_level: string;
  detection_model: string;
  detection_confidence: number;
  detection_iou: number;
  detection_imgsz: number;
  detection_device: string;
  counting_cooldown: number;
  counting_min_displacement: number;
  track_point: string;
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

export interface WebSocketMessage {
  type: 'count' | 'camera_status' | 'stats' | 'alert';
  payload: any;
  timestamp: string;
}

export type CameraStatus = 'online' | 'offline' | 'error' | 'connecting';

export interface CameraWithStatus {
  id: number;
  name: string;
  location: string | null;
  source_type: 'rtsp' | 'http' | 'file' | 'usb';
  source_url: string;
  enabled: boolean;
  username: string | null;
  password: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  detection_enabled: boolean;
  detection_confidence: number;
  detection_classes: number[] | null;
  zone_count: number;
  created_at: string;
  updated_at: string;
  status: CameraStatus;
  last_frame_at?: string | null;
  current_fps?: number;
  latency_ms?: number;
}

export interface DashboardStats {
  total_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  total_counts_today: number;
  total_in_today: number;
  total_out_today: number;
  active_zones: number;
}