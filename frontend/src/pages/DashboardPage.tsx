import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { type Camera, type LiveCount } from '../api/types';

interface DashboardStats {
  total_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  total_counts_today: number;
  total_in_today: number;
  total_out_today: number;
  active_zones: number;
}
import {
  VideoCameraIcon,
  ArrowPathIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  Squares2X2Icon,
  Cog6ToothIcon,
  PlayIcon,
  PauseIcon,
  EyeIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [liveCounts, setLiveCounts] = useState<Record<number, LiveCount>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      setError(null);
      const [statsRes, camerasRes] = await Promise.all([
        api.getCountStats({ interval: 'day' }),
        api.getCameras({ size: 50 }),
      ]);
      
      setStats({
        total_cameras: camerasRes.items?.length || 0,
        online_cameras: camerasRes.items?.filter((c: Camera) => c.status === 'online').length || 0,
        offline_cameras: camerasRes.items?.filter((c: Camera) => c.status === 'offline').length || 0,
        total_counts_today: (statsRes.total_in || 0) + (statsRes.total_out || 0),
        total_in_today: statsRes.total_in || 0,
        total_out_today: statsRes.total_out || 0,
        active_zones: 0,
      });
      setCameras(camerasRes.items || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در بارگذاری داده‌ها');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch live counts periodically
  const fetchLiveCounts = useCallback(async () => {
    try {
      const data = await api.getLiveCounts();
      const countsMap: Record<number, LiveCount> = {};
      data.forEach((item: LiveCount) => {
        countsMap[item.camera_id] = item;
      });
      setLiveCounts(countsMap);
    } catch (err) {
      console.error('Failed to fetch live counts:', err);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    fetchLiveCounts();
    const interval = setInterval(fetchLiveCounts, 5000);
    return () => clearInterval(interval);
  }, [fetchDashboardData, fetchLiveCounts]);

  const handleCameraClick = (camera: Camera) => {
    navigate(`/cameras/${camera.id}`);
  };

  const handleCameraToggle = async (camera: Camera) => {
    try {
      await api.toggleCamera(camera.id, !camera.enabled);
      setCameras((prev) =>
        prev.map((c) => (c.id === camera.id ? { ...c, enabled: !camera.enabled } : c))
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در تغییر وضعیت دوربین');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <svg className="spinner-lg" aria-hidden="true" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="card-body text-center py-12">
          <svg className="w-12 h-12 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">خطا در بارگذاری</h3>
          <p className="text-gray-500 mb-4">{error}</p>
          <button onClick={fetchDashboardData} className="btn-primary">
            تلاش مجدد
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل دوربین‌ها"
          value={stats?.total_cameras || 0}
          icon={VideoCameraIcon}
          color="blue"
          trend={stats ? `${stats.online_cameras} آنلاین، ${stats.offline_cameras} آفلاین` : undefined}
        />
        <StatCard
          title="ورود امروز"
          value={stats?.total_in_today || 0}
          icon={ArrowTrendingUpIcon}
          color="green"
          trend="افزایش نسبت به دیروز"
        />
        <StatCard
          title="خروج امروز"
          value={stats?.total_out_today || 0}
          icon={ArrowTrendingDownIcon}
          color="orange"
          trend="کاهش نسبت به دیروز"
        />
        <StatCard
          title="منطقه‌های فعال"
          value={stats?.active_zones || 0}
          icon={Squares2X2Icon}
          color="purple"
          trend="خطوط و مناطق شمارش"
        />
      </div>

      {/* Live Cameras Grid */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">نمای زنده دوربین‌ها</h2>
          <a href="/cameras" className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1">
            مشاهده همه
            <ArrowPathIcon className="w-4 h-4" />
          </a>
        </div>
        <div className="card-body p-0">
          {cameras.length === 0 ? (
            <div className="empty-state h-64">
              <VideoCameraIcon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">هیچ دوربینی یافت نشد</h3>
              <p className="empty-state-description">برای شروع، اولین دوربین خود را اضافه کنید</p>
              <button
                onClick={() => navigate('/cameras/new')}
                className="btn-primary mt-4"
              >
                افزودن دوربین
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-4">
              {cameras.map((camera) => (
                <CameraTile
                  key={camera.id}
                  camera={camera}
                  liveCount={liveCounts[camera.id]}
                  onClick={() => handleCameraClick(camera)}
                  onToggle={() => handleCameraToggle(camera)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">عملیات سریع</h2>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <QuickActionButton
              icon={VideoCameraIcon}
              title="افزودن دوربین"
              description="تنظیم دوربین جدید برای شمارش"
              onClick={() => navigate('/cameras/new')}
            />
            <QuickActionButton
              icon={Squares2X2Icon}
              title="تعریف منطقه"
              description="تعریف خطوط و مناطق شمارش"
              onClick={() => navigate('/zones')}
            />
            <QuickActionButton
              icon={ChartBarIcon}
              title="ساخت گزارش"
              description="استخراج گزارش اکسل یا PDF"
              onClick={() => navigate('/reports')}
            />
            <QuickActionButton
              icon={Cog6ToothIcon}
              title="تنظیمات"
              description="پیکربندی سیستم و کاربران"
              onClick={() => navigate('/settings')}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({
  title,
  value,
  icon: Icon,
  color,
  trend,
}: {
  title: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: 'blue' | 'green' | 'orange' | 'purple' | 'red';
  trend?: string;
}) {
  const colors = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    orange: 'bg-orange-100 text-orange-600',
    purple: 'bg-purple-100 text-purple-600',
    red: 'bg-red-100 text-red-600',
  };

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1 persian-numbers">{value.toLocaleString('fa-IR')}</p>
          {trend && <p className="text-xs text-gray-500 mt-1">{trend}</p>}
        </div>
        <div className={`${colors[color]} p-3 rounded-xl`}>
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}

// Camera Tile Component
interface CameraTileProps {
  camera: Camera;
  liveCount?: LiveCount;
  onClick: () => void;
  onToggle: () => void;
}

function CameraTile({ camera, liveCount, onClick, onToggle }: CameraTileProps) {
  const status = camera.status || (camera.enabled ? 'online' : 'offline');
  const isOnline = status === 'online';

  return (
    <div className="camera-tile group" onClick={onClick} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onClick()}>
      {/* Camera preview placeholder */}
      <div className="aspect-video bg-gray-800 relative overflow-hidden">
        {camera.source_type === 'file' ? (
          <div className="absolute inset-0 flex items-center justify-center text-gray-400">
            <VideoCameraIcon className="w-12 h-12" />
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500">
            <span className="text-sm">در حال اتصال...</span>
          </div>
        )}

        {/* Live indicator */}
        <div className="absolute top-2 end-2">
          <span className={`live-indicator ${isOnline ? 'online' : 'offline'}`}>
            {isOnline ? 'زنده' : 'آفلاین'}
          </span>
        </div>

        {/* Recording indicator if enabled */}
        {camera.detection_enabled && (
          <div className="absolute top-2 start-2 flex items-center gap-1 bg-red-500 text-white px-2 py-0.5 rounded text-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            تشخیص فعال
          </div>
        )}

        {/* Overlay with quick actions */}
        <div className="camera-tile-overlay">
          <div className="flex gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); onClick(); }}
              className="p-2 bg-white/90 rounded-lg text-gray-700 hover:bg-white transition-colors"
              aria-label="مشاهده جزئیات"
            >
              <EyeIcon className="w-5 h-5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onToggle(); }}
              className="p-2 bg-white/90 rounded-lg text-gray-700 hover:bg-white transition-colors"
              aria-label={camera.enabled ? 'غیرفعال کردن' : 'فعال کردن'}
            >
              {camera.enabled ? (
                <PauseIcon className="w-5 h-5" />
              ) : (
                <PlayIcon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Camera info */}
      <div className="p-3">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-gray-900 truncate pe-2">{camera.name}</h3>
          <span className={`badge ${isOnline ? 'badge-success' : 'badge-gray'}`}>
            {isOnline ? 'آنلاین' : 'آفلاین'}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Squares2X2Icon className="w-3.5 h-3.5" />
            {camera.live_fps?.toFixed(1) || '0.0'} FPS
          </span>
          {liveCount && (
            <>
              <span className="flex items-center gap-1 text-blue-600">
                <ArrowTrendingUpIcon className="w-3.5 h-3.5" />
                {liveCount.total_in}
              </span>
              <span className="flex items-center gap-1 text-orange-600">
                <ArrowTrendingDownIcon className="w-3.5 h-3.5" />
                {liveCount.total_out}
              </span>
            </>
          )}
        </div>
        {camera.location && (
          <p className="text-xs text-gray-400 truncate mt-1">{camera.location}</p>
        )}
      </div>
    </div>
  );
}

// Quick Action Button Component
function QuickActionButton({
  icon: Icon,
  title,
  description,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="card p-5 text-right hover:shadow-md transition-shadow group"
    >
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-200 transition-colors">
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
        <div>
          <h3 className="font-medium text-gray-900">{title}</h3>
          <p className="text-sm text-gray-500 mt-0.5">{description}</p>
        </div>
      </div>
    </button>
  );
}