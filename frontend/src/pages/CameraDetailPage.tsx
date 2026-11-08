import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/client';
import { type Camera, type Line, type Area, type LiveCount } from '../api/types';
import {
  ArrowLeftIcon,
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  Squares2X2Icon,
} from '@heroicons/react/24/outline';

export function CameraDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const cameraId = Number(id);

  const [camera, setCamera] = useState<Camera | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [live, setLive] = useState<LiveCount | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    if (!Number.isFinite(cameraId)) return;
    setLoading(true);
    setError(null);
    try {
      const cam = await api.getCamera(cameraId);
      setCamera(cam);
      const [l, a] = await Promise.all([api.getLines(cameraId), api.getAreas(cameraId)]);
      setLines(l);
      setAreas(a);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'دوربین یافت نشد');
    } finally {
      setLoading(false);
    }
  }, [cameraId]);

  const fetchLive = useCallback(async () => {
    if (!Number.isFinite(cameraId)) return;
    try {
      const all = await api.getLiveCounts();
      setLive(all.find((c) => c.camera_id === cameraId) || null);
    } catch {
      /* ignore */
    }
  }, [cameraId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    fetchLive();
    const t = setInterval(fetchLive, 5000);
    return () => clearInterval(t);
  }, [fetchLive]);

  const handleToggle = async () => {
    if (!camera) return;
    try {
      const updated = await api.toggleCamera(camera.id, !camera.enabled);
      setCamera(updated);
    } catch (err) {
      console.error('Failed to toggle camera:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <svg className="spinner-lg" />
      </div>
    );
  }

  if (error || !camera) {
    return (
      <div className="card">
        <div className="card-body text-center py-12">
          <h3 className="text-lg font-medium text-gray-900 mb-2">{error || 'دوربین یافت نشد'}</h3>
          <button onClick={() => navigate('/cameras')} className="btn-secondary mt-2">
            بازگشت به فهرست دوربین‌ها
          </button>
        </div>
      </div>
    );
  }

  const isOnline = camera.status === 'online';
  const streamUrl = api.getCameraStreamUrl(camera.id);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/cameras')}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
            aria-label="بازگشت"
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{camera.name}</h1>
            <p className="text-gray-500 mt-0.5">{camera.location || 'بدون موقعیت'}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchAll} className="btn-secondary">
            <ArrowPathIcon className="w-5 h-5 ml-2" />
            بارگذاری مجدد
          </button>
          <button onClick={handleToggle} className={camera.enabled ? 'btn-secondary' : 'btn-primary'}>
            {camera.enabled ? (
              <>
                <PauseIcon className="w-5 h-5 ml-2" />
                غیرفعال کردن
              </>
            ) : (
              <>
                <PlayIcon className="w-5 h-5 ml-2" />
                فعال کردن
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live stream */}
        <div className="lg:col-span-2 card overflow-hidden">
          <div className="aspect-video bg-gray-900 relative">
            {isOnline && camera.enabled ? (
              <img
                src={streamUrl}
                alt={`نمای زنده ${camera.name}`}
                className="w-full h-full object-contain"
                onError={() => setError('پخش زنده در دسترس نیست')}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 gap-2">
                <Squares2X2Icon className="w-12 h-12" />
                <span className="text-sm">{camera.enabled ? 'دوربین آفلاین است' : 'دوربین غیرفعال است'}</span>
                {camera.last_error && <span className="text-xs text-red-400">{camera.last_error}</span>}
              </div>
            )}
            <div className="absolute top-2 right-2">
              <span className={`live-indicator ${isOnline ? 'online' : 'offline'}`}>
                {isOnline ? 'زنده' : 'آفلاین'}
              </span>
            </div>
          </div>
        </div>

        {/* Side stats */}
        <div className="space-y-4">
          <div className="card p-5">
            <h3 className="text-sm font-medium text-gray-500 mb-3">آمار زنده</h3>
            <div className="space-y-2">
              <StatRow label="تعداد حاضر" value={live?.current_count ?? 0} />
              <StatRow label="ورود" value={live?.total_in ?? 0} color="text-green-600" />
              <StatRow label="خروج" value={live?.total_out ?? 0} color="text-orange-600" />
              <StatRow label="FPS" value={camera.live_fps ? camera.live_fps.toFixed(1) : '0.0'} />
            </div>
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-medium text-gray-500 mb-3">مناطق شمارش</h3>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">خطوط شمارش</span>
                <span className="font-medium">{lines.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">مناطق شمارش</span>
                <span className="font-medium">{areas.length}</span>
              </div>
            </div>
            <button
              onClick={() => navigate(`/zones?camera=${camera.id}`)}
              className="btn-outline btn-sm w-full mt-4"
            >
              مدیریت مناطق
            </button>
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-medium text-gray-500 mb-3">مشخصات اتصال</h3>
            <div className="space-y-1 text-sm font-mono text-gray-600 break-all">
              <p>{camera.source_type === 'file' ? camera.file_path : camera.rtsp_url || `${camera.host || ''}:${camera.port || ''}`}</p>
              <p className="text-xs text-gray-400 mt-2">محدودیت FPS: {camera.fps_limit}</p>
              <p className="text-xs text-gray-400">
                تشخیص: {camera.detection_enabled ? 'فعال' : 'غیرفعال'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatRow({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-lg font-bold persian-numbers ${color || 'text-gray-900'}`}>{value}</span>
    </div>
  );
}
