import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Pencil, Play, Plus, Pause, ScanLine, Search, Trash2, Video, PlugZap } from 'lucide-react';
import api from '@/api/client';
import { type Camera, type CameraCreate, type TestConnectionResult } from '@/api/types';
import { fa, faNumber } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Alert } from '@/components/ui/alert';
import { Field, Input } from '@/components/ui/input';
import { StatusDot } from '@/components/AppShell';

type CameraForm = CameraCreate & {
  mode: 'manual' | 'url' | 'file';
  port: number;
  rtsp_path: string;
};

const emptyForm = (): CameraForm => ({
  name: '',
  location: '',
  mode: 'url',
  host: '',
  port: 554,
  username: '',
  password: '',
  rtsp_path: '',
  url: '',
  file_path: '',
  fps_limit: 10,
  detection_enabled: true,
  enabled: true,
});

const MODES: Array<{ value: CameraForm['mode']; label: string }> = [
  { value: 'url', label: 'آدرس کامل RTSP' },
  { value: 'manual', label: 'IP + کاربر + رمز' },
  { value: 'file', label: 'فایل ویدیویی (شبیه‌سازی)' },
];

export function CamerasPage() {
  const navigate = useNavigate();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Camera | null>(null);
  const [form, setForm] = useState<CameraForm>(emptyForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ camera: string; ok: boolean; text: string } | null>(null);

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getCameras({ page, size: 20, search: search || undefined });
      const start = (page - 1) * 20;
      setCameras(res.items.slice(start, start + 20));
      setPages(res.pages);
      setTotal(res.total);
    } catch {
      /* خطا در جدول خالی نمایش داده می‌شود */
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm());
    setErrors({});
    setModal(true);
  }

  function openEdit(cam: Camera) {
    setEditing(cam);
    setForm({
      name: cam.name,
      location: cam.location || '',
      mode: cam.source_type === 'file' ? 'file' : 'manual',
      host: cam.host || '',
      port: cam.port || 554,
      username: cam.username || '',
      password: '',
      rtsp_path: cam.rtsp_path || '',
      url: '',
      file_path: cam.file_path || '',
      fps_limit: cam.fps_limit || 10,
      detection_enabled: cam.detection_enabled,
      enabled: cam.enabled,
    });
    setErrors({});
    setModal(true);
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'نام دوربین الزامی است';
    if (form.mode === 'url' && !(form.url || '').trim()) e.url = 'آدرس RTSP الزامی است';
    if (form.mode === 'manual' && !(form.host || '').trim()) e.host = 'آدرس IP الزامی است';
    if (form.mode === 'file' && !(form.file_path || '').trim()) e.file_path = 'مسیر فایل الزامی است';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      const data: CameraCreate = {
        name: form.name,
        location: form.location,
        mode: form.mode,
        fps_limit: form.fps_limit,
        detection_enabled: form.detection_enabled,
        enabled: form.enabled,
      };
      if (form.mode === 'url') data.url = form.url;
      else if (form.mode === 'file') data.file_path = form.file_path;
      else {
        data.host = form.host;
        data.port = form.port;
        data.username = form.username || undefined;
        data.rtsp_path = form.rtsp_path || '';
      }
      if (form.password) data.password = form.password;

      if (editing) await api.updateCamera(editing.id, data);
      else await api.createCamera(data);
      setModal(false);
      fetchCameras();
    } catch (err: any) {
      setErrors({ submit: err.response?.data?.detail || 'خطا در ذخیره دوربین' });
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(cam: Camera) {
    try {
      await api.toggleCamera(cam.id, !cam.enabled);
      setCameras((prev) => prev.map((c) => (c.id === cam.id ? { ...c, enabled: !cam.enabled } : c)));
    } catch {
      /* بی‌صدا */
    }
  }

  async function handleDelete(cam: Camera) {
    if (!window.confirm(`دوربین «${cam.name}» حذف شود؟ این عمل بازگشت‌پذیر نیست.`)) return;
    try {
      await api.deleteCamera(cam.id);
      setCameras((prev) => prev.filter((c) => c.id !== cam.id));
      setTotal((t) => t - 1);
    } catch {
      /* بی‌صدا */
    }
  }

  async function handleTest(cam: Camera) {
    setTestingId(cam.id);
    setTestResult(null);
    try {
      const r: TestConnectionResult = await api.testCameraConnection(cam.id);
      setTestResult({
        camera: cam.name,
        ok: r.ok,
        text: r.ok
          ? `اتصال موفق - رزولوشن ${fa(r.width)}×${fa(r.height)}، ${fa(Math.round(r.fps))} فریم بر ثانیه`
          : r.message || 'اتصال برقرار نشد',
      });
    } catch (err: any) {
      setTestResult({ camera: cam.name, ok: false, text: err.response?.data?.detail || 'خطا در آزمایش اتصال' });
    } finally {
      setTestingId(null);
    }
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-lg font-bold">مدیریت دوربین‌ها</h1>
          <p className="text-sm text-muted-foreground">
            {faNumber(total)} دوربین ثبت شده
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          افزودن دوربین
        </Button>
      </div>

      {testResult && (
        <Alert variant={testResult.ok ? 'success' : 'destructive'} title={`آزمایش اتصال «${testResult.camera}»`}>
          {testResult.text}
        </Alert>
      )}

      <Card>
        <CardContent className="pt-5">
          <div className="relative">
            <Search className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              className="ps-9"
              placeholder="جستجو در نام، مکان یا آدرس…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        {loading && cameras.length === 0 ? (
          <CardContent className="space-y-3 pt-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-field bg-secondary/60" />
            ))}
          </CardContent>
        ) : cameras.length === 0 ? (
          <CardContent className="pt-5">
            <EmptyState
              icon={Video}
              title={search ? 'نتیجه‌ای یافت نشد' : 'هنوز دوربینی ثبت نشده است'}
              description={search ? 'عبارت دیگری را جستجو کنید.' : 'اولین دوربین را با آدرس RTSP یا فایل ویدیویی اضافه کنید.'}
              action={
                !search && (
                  <Button onClick={openCreate}>
                    <Plus className="size-4" />
                    افزودن دوربین
                  </Button>
                )
              }
            />
          </CardContent>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-line border-b border-border text-start text-xs text-muted-foreground">
                  <th className="px-4 py-3 text-start font-medium">دوربین</th>
                  <th className="px-4 py-3 text-start font-medium">منبع</th>
                  <th className="px-4 py-3 text-start font-medium">وضعیت</th>
                  <th className="hidden px-4 py-3 text-start font-medium md:table-cell">فریم/ث</th>
                  <th className="px-4 py-3 text-start font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map((cam) => (
                  <tr key={cam.id} className="border-line border-b border-border/60 transition-colors last:border-0 hover:bg-accent/40">
                    <td className="px-4 py-3">
                      <p className="font-medium">{cam.name}</p>
                      {cam.location && <p className="text-xs text-muted-foreground">{cam.location}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={cam.source_type === 'file' ? 'warning' : 'brand'}>
                        {cam.source_type === 'file' ? 'فایل' : 'RTSP'}
                      </Badge>
                      <p className="ltr-nums mt-0.5 max-w-56 truncate text-[11px] text-muted-foreground">
                        {cam.source_type === 'file' ? cam.file_path : cam.rtsp_url || `${cam.host ?? ''}:${cam.port ?? ''}`}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      {cam.enabled ? <StatusDot status={cam.status} /> : <Badge variant="secondary">غیرفعال</Badge>}
                    </td>
                    <td className="ltr-nums hidden px-4 py-3 tabular-nums text-muted-foreground md:table-cell">
                      {fa(cam.live_fps?.toFixed(1) ?? '۰٫۰')}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className="size-8" aria-label="آزمایش اتصال" disabled={testingId === cam.id} onClick={() => handleTest(cam)}>
                          <PlugZap className="size-4" strokeWidth={1.75} />
                        </Button>
                        <Button variant="ghost" size="icon" className="size-8" aria-label="خطوط و مناطق" onClick={() => navigate(`/zones?camera=${cam.id}`)}>
                          <ScanLine className="size-4" strokeWidth={1.75} />
                        </Button>
                        <Button variant="ghost" size="icon" className="size-8" aria-label="ویرایش" onClick={() => openEdit(cam)}>
                          <Pencil className="size-4" strokeWidth={1.75} />
                        </Button>
                        <Button variant="ghost" size="icon" className="size-8" aria-label={cam.enabled ? 'غیرفعال کردن' : 'فعال کردن'} onClick={() => handleToggle(cam)}>
                          {cam.enabled ? <Pause className="size-4" strokeWidth={1.75} /> : <Play className="size-4" strokeWidth={1.75} />}
                        </Button>
                        <Button variant="ghost" size="icon" className="size-8 text-destructive hover:text-destructive" aria-label="حذف" onClick={() => handleDelete(cam)}>
                          <Trash2 className="size-4" strokeWidth={1.75} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {pages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            صفحه {fa(page)} از {fa(pages)}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              قبلی
            </Button>
            <Button variant="outline" size="sm" disabled={page === pages} onClick={() => setPage((p) => p + 1)}>
              بعدی
            </Button>
          </div>
        </div>
      )}

      {/* پنجره افزودن/ویرایش */}
      <Dialog
        open={modal}
        onOpenChange={setModal}
        title={editing ? 'ویرایش دوربین' : 'افزودن دوربین جدید'}
        description="مشخصات منبع تصویر را وارد کنید؛ رمز عبور به‌صورت رمزنگاری‌شده ذخیره می‌شود."
        className="max-w-lg"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {errors.submit && <Alert variant="destructive">{errors.submit}</Alert>}

          <Field label="نام دوربین" htmlFor="cam-name">
            <Input id="cam-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={errors.name} placeholder="مثلاً ورودی اصلی" data-autofocus />
          </Field>

          <Field label="موقعیت" htmlFor="cam-location" hint="اختیاری - مثلاً لابی طبقه اول">
            <Input id="cam-location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </Field>

          <Field label="نوع اتصال" htmlFor="cam-mode">
            <select
              id="cam-mode"
              value={form.mode}
              onChange={(e) => setForm({ ...form, mode: e.target.value as CameraForm['mode'] })}
              className="h-10 w-full rounded-field border-line-field border-input bg-field px-3 text-sm shadow-field transition-colors focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </Field>

          {form.mode === 'url' && (
            <Field label="آدرس RTSP" htmlFor="cam-url" hint="rtsp://user:pass@ip:554/stream">
              <Input id="cam-url" dir="ltr" className="ltr-nums font-mono text-xs" value={form.url || ''} onChange={(e) => setForm({ ...form, url: e.target.value })} error={errors.url} />
            </Field>
          )}

          {form.mode === 'file' && (
            <Field label="مسیر فایل ویدیو" htmlFor="cam-file" hint="مسیر فایل روی سرور، مثلاً data/sample/sample_walk.mp4">
              <Input id="cam-file" dir="ltr" className="ltr-nums font-mono text-xs" value={form.file_path || ''} onChange={(e) => setForm({ ...form, file_path: e.target.value })} error={errors.file_path} />
            </Field>
          )}

          {form.mode === 'manual' && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Field label="آدرس IP" htmlFor="cam-host">
                    <Input id="cam-host" dir="ltr" className="ltr-nums font-mono text-xs" value={form.host || ''} onChange={(e) => setForm({ ...form, host: e.target.value })} error={errors.host} placeholder="192.168.1.64" />
                  </Field>
                </div>
                <Field label="پورت" htmlFor="cam-port">
                  <Input id="cam-port" type="number" min={1} max={65535} value={form.port} onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) || 554 })} />
                </Field>
              </div>
              <Field label="مسیر RTSP" htmlFor="cam-path" hint="مثلاً /stream1 یا /Streaming/Channels/101">
                <Input id="cam-path" dir="ltr" className="ltr-nums font-mono text-xs" value={form.rtsp_path || ''} onChange={(e) => setForm({ ...form, rtsp_path: e.target.value })} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="نام کاربری" htmlFor="cam-user">
                  <Input id="cam-user" dir="ltr" autoComplete="off" value={form.username || ''} onChange={(e) => setForm({ ...form, username: e.target.value })} />
                </Field>
                <Field label="رمز عبور" htmlFor="cam-pass" hint={editing ? 'خالی بگذارید تا تغییر نکند' : undefined}>
                  <Input id="cam-pass" type="password" autoComplete="new-password" value={form.password || ''} onChange={(e) => setForm({ ...form, password: e.target.value })} />
                </Field>
              </div>
            </>
          )}

          <Field label="محدودیت نرخ فریم" htmlFor="cam-fps" hint="حداکثر فریم پردازش‌شده در ثانیه (۱ تا ۶۰)">
            <Input id="cam-fps" type="number" min={1} max={60} value={form.fps_limit} onChange={(e) => setForm({ ...form, fps_limit: parseFloat(e.target.value) || 10 })} />
          </Field>

          <div className="flex flex-wrap gap-5 border-line border-t border-border pt-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={form.detection_enabled} onChange={(e) => setForm({ ...form, detection_enabled: e.target.checked })} className="size-4 accent-[var(--brand)]" />
              تشخیص اشیا فعال باشد
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="size-4 accent-[var(--brand)]" />
              دوربین فعال باشد
            </label>
          </div>

          <div className="flex gap-2 border-line border-t border-border pt-4">
            <Button type="submit" disabled={saving}>
              <Check className="size-4" />
              {saving ? 'در حال ذخیره…' : editing ? 'به‌روزرسانی' : 'افزودن'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setModal(false)}>
              انصراف
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
