import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpLeft, Pause, Play, Plus, ScanLine, Video } from 'lucide-react';
import api from '@/api/client';
import { type Camera, type LiveCount } from '@/api/types';
import { fa, faNumber, faRelativeTime } from '@/lib/utils';
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

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<TodayStats | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [live, setLive] = useState<Record<number, LiveCount>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const [statsRes, camsRes] = await Promise.all([
        api.getCountStats({ interval: 'day' }),
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

  const fetchLive = useCallback(async () => {
    try {
      const data = await api.getLiveCounts();
      setLive(Object.fromEntries(data.map((c) => [c.camera_id, c])));
    } catch {
      /* پیش‌بینی: نمایش بی‌صدا؛ دوره‌ی بعد دوباره تلاش می‌شود */
    }
  }, []);

  useEffect(() => {
    fetchAll();
    fetchLive();
    const t = setInterval(fetchLive, 5000);
    return () => clearInterval(t);
  }, [fetchAll, fetchLive]);

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

  const kpis = [
    { label: 'ورود امروز', value: faNumber(stats?.total_in ?? 0), trend },
    { label: 'خروج امروز', value: faNumber(stats?.total_out ?? 0), trend: trend.map((v) => -v) },
    { label: 'افراد حاضر (خالص)', value: faNumber(stats?.net_count ?? 0) },
    { label: 'دوربین‌های آنلاین', value: `${faNumber(online)} از ${faNumber(cameras.length)}` },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-lg font-bold">داشبورد</h1>
          <p className="text-sm text-muted-foreground">نمای کلی سامانه و شمارش زنده</p>
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
              {cameras.map((cam) => (
                <CameraTile key={cam.id} camera={cam} live={live[cam.id]} onToggle={() => toggleCamera(cam)} />
              ))}
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
    </div>
  );
}

function CameraTile({ camera, live, onToggle }: { camera: Camera; live?: LiveCount; onToggle: () => void }) {
  const isOnline = camera.status === 'online';
  const [hover, setHover] = useState(false);

  return (
    <div
      className="group overflow-hidden rounded-surface border-line border-border bg-card"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className="relative aspect-video bg-black">
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
        </div>

        {hover && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/50">
            <Button size="sm" variant="secondary" onClick={onToggle}>
              {camera.enabled ? <Pause className="size-4" /> : <Play className="size-4" />}
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
