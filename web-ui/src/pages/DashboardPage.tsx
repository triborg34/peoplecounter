import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowDownLeft,
  ArrowUpLeft,
  Cpu,
  HardDrive,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  Plus,
  ScanLine,
  Video,
} from 'lucide-react';
import api from '@/api/client';
import { type Camera, type LiveCount } from '@/api/types';
import { useLiveCounts } from '@/lib/useLiveCounts';
import { cn, fa, faNumber, faRelativeTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { DashboardStats } from '@/components/ui/dashboard-stats';
import { Alert } from '@/components/ui/alert';
import { StatusDot } from '@/components/AppShell';

interface TodayStats {
  total_in: number;
  total_out: number;
  net_count: number;
  timeline: Array<Record<string, unknown>>;
}

interface HardwareStats {
  cpu: { percent: number };
  ram: { percent: number; used_gb: number; total_gb: number };
  disk: { percent: number; used_gb: number; total_gb: number };
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<TodayStats | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [enlargedCameraId, setEnlargedCameraId] = useState<number | null>(null);
  const [hardware, setHardware] = useState<HardwareStats | null>(null);

  // Live pushes from /ws/counts: counts update without a page refresh.
  const { live, eventTick, connected } = useLiveCounts();

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const [statsRes, camsRes] = await Promise.all([
        api.getCountStats({ today: true }),
        api.getCameras({ size: 100 }),
      ]);
      setStats(statsRes);
      setCameras(camsRes.items);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در بارگذاری داشبورد');
    } finally {
      setLoading(false);
    }
  }, []);

  // Today's totals: fetched once, then refreshed whenever the socket reports
  // new crossings (throttled inside the hook) so the KPI cards stay current.
  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.getCountStats({ today: true }));
    } catch {
      /* keep the previous numbers rather than blanking the cards */
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Today's totals timer
  useEffect(() => {
    const id = window.setInterval(refreshStats, 4000);
    return () => window.clearInterval(id);
  }, [refreshStats]);

  useEffect(() => {
    if (eventTick > 0) refreshStats();
  }, [eventTick, refreshStats]);

  // Periodically fetch hardware metrics (CPU, RAM, Disk)
  useEffect(() => {
    let mounted = true;
    const fetchHw = async () => {
      try {
        const data = await api.getSystemHardware();
        if (mounted) setHardware(data);
      } catch {
        /* ignore */
      }
    };
    fetchHw();
    const id = window.setInterval(fetchHw, 4000);
    return () => {
      mounted = false;
      window.clearInterval(id);
    };
  }, []);

  async function toggleCamera(cam: Camera) {
    try {
      await api.toggleCamera(cam.id, !cam.enabled);
      setCameras((prev) => prev.map((c) => (c.id === cam.id ? { ...c, enabled: !cam.enabled } : c)));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در تغییر وضعیت دوربین');
    }
  }

  const online = cameras.filter((c) => c.status === 'online').length;
  const trend = (stats?.timeline ?? []).slice(-12).map((t) => Number(t.total ?? t.count ?? t.in ?? 0));

  const totalPeople = (stats?.total_in ?? 0) + (stats?.total_out ?? 0);

  const kpis = [
    { label: 'ورود امروز', value: faNumber(stats?.total_in ?? 0), trend },
    { label: 'خروج امروز', value: faNumber(stats?.total_out ?? 0), trend: trend.map((v) => -v) },
    // Every crossing (IN + OUT), not the net difference.
    { label: 'كل افراد', value: faNumber(totalPeople) },
    { label: 'دوربین‌های آنلاین', value: `${faNumber(online)} از ${faNumber(cameras.length)}` },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-lg font-bold">داشبورد</h1>
          <p className="text-sm text-muted-foreground">
            نمای کلی سامانه و شمارش زنده
            <span className="ms-2 inline-flex items-center gap-1 text-[11px]">
              <span
                className={`size-1.5 rounded-full ${connected ? 'animate-pulse bg-success' : 'bg-muted-foreground/50'}`}
                aria-hidden
              />
              {connected ? 'به‌روزرسانی زنده' : 'حالت دوره‌ای'}
            </span>
          </p>
        </div>
        <Button onClick={() => navigate('/cameras')} size="sm" variant="outline">
          <Plus className="size-4" />
          دوربین جدید
        </Button>
      </div>

      {error && <Alert variant="destructive" title="خطا">{error}</Alert>}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-card" />
          ))}
        </div>
      ) : (
        <DashboardStats items={kpis} />
      )}

      {/* کاشی‌های زنده */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>نمای زنده دوربین‌ها</CardTitle>
          <Link to="/cameras" className="text-xs text-muted-foreground transition-colors hover:text-foreground">
            مشاهده همه
          </Link>
        </CardHeader>
        <CardContent>
          {cameras.length === 0 ? (
            <EmptyState
              icon={Video}
              title="هنوز دوربینی ثبت نشده است"
              description="برای شروع، یک دوربین RTSP یا فایل ویدیویی آزمایشی اضافه کنید."
              action={
                <Button onClick={() => navigate('/cameras')}>
                  <Plus className="size-4" />
                  افزودن دوربین
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {cameras.map((cam) => {
                const isEnlarged = enlargedCameraId === cam.id;
                return (
                  <div
                    key={cam.id}
                    className={cn(
                      'transition-all duration-300',
                      isEnlarged && 'sm:col-span-2 xl:col-span-2 sm:row-span-2 scale-[1.01] z-10 ring-2 ring-brand/50 rounded-surface'
                    )}
                  >
                    <CameraTile
                      camera={cam}
                      live={live[cam.id]}
                      isEnlarged={isEnlarged}
                      onToggle={() => toggleCamera(cam)}
                      onToggleEnlarge={() => setEnlargedCameraId(isEnlarged ? null : cam.id)}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* میان‌برها */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <QuickLink to="/zones" icon={ScanLine} title="خطوط و مناطق شمارش" desc="رسم خط و منطقه روی تصویر دوربین" />
        <QuickLink to="/reports" icon={ArrowUpLeft} title="گزارش‌ها و خروجی" desc="نمودار، جدول و خروجی CSV/Excel/PDF" />
        <QuickLink to="/settings" icon={ArrowDownLeft} title="تنظیمات سامانه" desc="کاربران، سرویس API و پیکربندی موتور" />
      </div>

      {/* پایش سخت‌افزار سرور (۳ نمودار مینیمال CPU / RAM / Disk) */}
      <Card>
        <CardHeader className="py-3.5">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Activity className="size-4 text-brand" />
            <span>پایش سخت‌افزار سامانه</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <HardwareGauge
              percent={hardware?.cpu.percent ?? 0}
              label="پردازنده (CPU)"
              sublabel={`${faNumber(Math.round(hardware?.cpu.percent ?? 0))}٪ بار پردازشی لحظه‌ای`}
              icon={Cpu}
            />
            <HardwareGauge
              percent={hardware?.ram.percent ?? 0}
              label="حافظه رم (RAM)"
              sublabel={`${fa(hardware?.ram.used_gb ?? '۰٫۰')} از ${fa(hardware?.ram.total_gb ?? '۰٫۰')} گیگابایت`}
              icon={Activity}
            />
            <HardwareGauge
              percent={hardware?.disk.percent ?? 0}
              label="فضای دیسک (Disk)"
              sublabel={`${fa(hardware?.disk.used_gb ?? '۰')} از ${fa(hardware?.disk.total_gb ?? '۰')} گیگابایت`}
              icon={HardDrive}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CameraTile({
  camera,
  live,
  isEnlarged,
  onToggle,
  onToggleEnlarge,
}: {
  camera: Camera;
  live?: LiveCount;
  isEnlarged?: boolean;
  onToggle: () => void;
  onToggleEnlarge: () => void;
}) {
  const isOnline = camera.status === 'online';
  const [hover, setHover] = useState(false);

  return (
    <div
      className={cn(
        'group overflow-hidden rounded-surface border-line border-border bg-card transition-shadow',
        isEnlarged && 'shadow-lg'
      )}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div
        className="relative aspect-video bg-black cursor-pointer select-none"
        onClick={onToggleEnlarge}
        title={isEnlarged ? 'برای کوچک‌نمایی کلیک کنید' : 'برای بزرگ‌نمایی کلیک کنید'}
      >
        {isOnline ? (
          <img
            src={api.getCameraStreamUrl(camera.id)}
            alt={`تصویر زنده ${camera.name}`}
            className="size-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex size-full items-center justify-center text-muted-foreground/60">
            <Video className="size-8" strokeWidth={1.5} />
          </div>
        )}
        <div className="absolute top-2 start-2 flex items-center gap-1.5">
          <span className="rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur-sm">
            {isOnline ? 'زنده' : 'آفلاین'}
          </span>
          {camera.detection_enabled && (
            <span className="flex items-center gap-1 rounded-full bg-destructive/90 px-2 py-0.5 text-[10px] font-medium text-white">
              <span className="size-1.5 animate-pulse rounded-full bg-white" aria-hidden />
              تشخیص فعال
            </span>
          )}
          {isEnlarged && (
            <span className="rounded-full bg-brand px-2 py-0.5 text-[10px] font-medium text-white shadow-sm">
              بزرگ‌نمایی
            </span>
          )}
        </div>

        {/* دکمه بزرگ‌نمایی / کوچک‌نمایی در گوشه */}
        <div className="absolute top-2 end-2">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleEnlarge();
            }}
            className="flex size-7 items-center justify-center rounded-full bg-black/60 text-white/90 backdrop-blur-sm transition-colors hover:bg-black/90 hover:text-white"
            title={isEnlarged ? 'کوچک کردن' : 'بزرگ کردن تصویر'}
          >
            {isEnlarged ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
          </button>
        </div>

        {hover && (
          <div
            className="absolute inset-0 flex items-center justify-center gap-2 bg-black/40 transition-opacity"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              size="sm"
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation();
                onToggle();
              }}
            >
              {camera.enabled ? <Pause className="size-4" /> : <Play className="size-4" />}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="bg-card/90 text-xs backdrop-blur-sm"
              onClick={(e) => {
                e.stopPropagation();
                onToggleEnlarge();
              }}
            >
              {isEnlarged ? (
                <>
                  <Minimize2 className="size-3.5 ml-1" />
                  کوچک‌نمایی
                </>
              ) : (
                <>
                  <Maximize2 className="size-3.5 ml-1" />
                  بزرگ‌نمایی
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-1.5 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-medium">{camera.name}</p>
          <StatusDot status={camera.status} />
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="ltr-nums tabular-nums">{fa(camera.live_fps?.toFixed(1) ?? '۰٫۰')} فریم/ث</span>
          {live && (
            <>
              <span className="inline-flex items-center gap-0.5 text-success">
                <ArrowUpLeft className="size-3.5" />
                {faNumber(live.total_in)}
              </span>
              <span className="inline-flex items-center gap-0.5 text-warning">
                <ArrowDownLeft className="size-3.5" />
                {faNumber(live.total_out)}
              </span>
              {live.last_event && (
                <span className="truncate">آخرین: {faRelativeTime(live.last_event.timestamp)}</span>
              )}
            </>
          )}
        </div>
        {camera.location && <p className="truncate text-[11px] text-muted-foreground/70">{camera.location}</p>}
      </div>
    </div>
  );
}

function HardwareGauge({
  percent,
  label,
  sublabel,
  icon: Icon,
}: {
  percent: number;
  label: string;
  sublabel: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
}) {
  const p = Math.min(100, Math.max(0, percent));
  const r = 26;
  const c = 2 * Math.PI * r;
  const offset = c - (p / 100) * c;
  const strokeColor = p > 85 ? '#ef4444' : p > 65 ? '#f59e0b' : 'var(--brand)';

  return (
    <div className="flex items-center gap-4 rounded-surface border-line border-border bg-card/60 p-4 transition-colors hover:bg-card">
      <div className="relative flex size-16 shrink-0 items-center justify-center">
        <svg className="size-full -rotate-90" viewBox="0 0 64 64">
          <circle
            cx="32"
            cy="32"
            r={r}
            className="stroke-muted/30"
            strokeWidth="5"
            fill="transparent"
          />
          <circle
            cx="32"
            cy="32"
            r={r}
            stroke={strokeColor}
            strokeWidth="5"
            strokeDasharray={c}
            strokeDashoffset={offset}
            strokeLinecap="round"
            fill="transparent"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="font-display text-xs font-bold tabular-nums">
            {faNumber(Math.round(p))}٪
          </span>
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
          <Icon className="size-4 text-brand" strokeWidth={1.75} />
          <span className="font-medium text-foreground">{label}</span>
        </div>
        <p className="truncate text-xs text-muted-foreground tabular-nums">
          {sublabel}
        </p>
      </div>
    </div>
  );
}

function QuickLink({ to, icon: Icon, title, desc }: { to: string; icon: React.ComponentType<{ className?: string; strokeWidth?: number }>; title: string; desc: string }) {
  return (
    <Link
      to={to}
      className="group flex items-start gap-3 rounded-surface border-line border-border bg-card p-4 transition-colors duration-(--motion) ease-motion hover:bg-accent"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-control bg-secondary">
        <Icon className="size-5 text-brand" strokeWidth={1.75} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold">{title}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">{desc}</span>
      </span>
    </Link>
  );
}
