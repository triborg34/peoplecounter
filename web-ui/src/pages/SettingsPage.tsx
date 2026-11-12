import { useCallback, useEffect, useState } from 'react';
import { Check, Cpu, KeyRound, Server } from 'lucide-react';
import api from '@/api/client';
import { useAuth } from '@/contexts/AuthContext';
import { fa } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert } from '@/components/ui/alert';
import { Field, Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

interface SystemStatus {
  status: string;
  version: string;
  engine_running: boolean;
  detector_available: boolean;
}

export function SettingsPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [statusError, setStatusError] = useState('');
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      setStatus((await api.getSystemStatus()) as SystemStatus);
      setStatusError('');
    } catch {
      setStatusError('سرویس در دسترس نیست؛ مطمئن شوید سرور API اجرا شده است.');
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    if (next.length < 6) {
      setFeedback({ ok: false, text: 'رمز جدید حداقل ۶ نویسه باشد' });
      return;
    }
    if (next !== repeat) {
      setFeedback({ ok: false, text: 'تکرار رمز عبور مطابقت ندارد' });
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      await api.changePassword(current, next);
      setFeedback({ ok: true, text: 'رمز عبور با موفقیت تغییر کرد' });
      setCurrent('');
      setNext('');
      setRepeat('');
    } catch (err: any) {
      setFeedback({ ok: false, text: err.response?.data?.detail || 'خطا در تغییر رمز عبور' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="font-display text-lg font-bold">تنظیمات</h1>
        <p className="text-sm text-muted-foreground">وضعیت سامانه و امنیت حساب</p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* وضعیت سامانه */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Server className="size-4 text-brand" strokeWidth={1.75} />
              وضعیت سرور
            </CardTitle>
            {status && <Badge variant={status.status === 'ok' ? 'success' : 'warning'}>{status.status === 'ok' ? 'سالم' : status.status}</Badge>}
          </CardHeader>
          <CardContent className="space-y-3">
            {statusError ? (
              <Alert variant="warning">{statusError}</Alert>
            ) : !status ? (
              <div className="h-16 animate-pulse rounded-field bg-secondary/60" />
            ) : (
              <ul className="space-y-2.5 text-sm">
                <StatusRow icon={Server} label="نسخه سامانه" value={status.version ? fa(status.version) : '—'} />
                <StatusRow
                  icon={Cpu}
                  label="موتور تشخیص"
                  value={status.engine_running ? 'در حال اجرا' : 'متوقف'}
                  good={status.engine_running}
                />
                <StatusRow
                  icon={Cpu}
                  label="مدل تشخیص (YOLO)"
                  value={status.detector_available ? 'بارگذاری شده' : 'در دسترس نیست'}
                  good={status.detector_available}
                />
              </ul>
            )}
            {!statusError && status && !status.detector_available && (
              <Alert variant="warning" title="مدل تشخیص در دسترس نیست">
                در اولین اجرا وزن‌های yolov8n.pt دانلود می‌شوند؛ چند لحظه صبر کنید و صفحه را بازخوانی کنید.
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* تغییر رمز */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="size-4 text-brand" strokeWidth={1.75} />
              تغییر رمز عبور
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={changePassword} className="space-y-4">
              {feedback && <Alert variant={feedback.ok ? 'success' : 'destructive'}>{feedback.text}</Alert>}

              <Field label="رمز عبور فعلی" htmlFor="cur-pass">
                <Input id="cur-pass" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
              </Field>
              <Field label="رمز عبور جدید" htmlFor="new-pass" hint="حداقل ۶ نویسه">
                <Input id="new-pass" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
              </Field>
              <Field label="تکرار رمز جدید" htmlFor="rep-pass">
                <Input id="rep-pass" type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} />
              </Field>

              <Button type="submit" disabled={saving}>
                <Check className="size-4" />
                {saving ? 'در حال ذخیره…' : 'تغییر رمز'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>حساب کاربری</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Info label="نام کاربری" value={user?.username ?? '—'} ltr />
          <Info label="نام کامل" value={user?.full_name || '—'} />
          <Info label="نقش" value={user?.role === 'admin' ? 'مدیر سیستم' : user?.role === 'operator' ? 'اپراتور' : 'بیننده'} />
          <Info label="ایمیل" value={user?.email || '—'} ltr />
        </CardContent>
      </Card>
    </div>
  );
}

function StatusRow({ icon: Icon, label, value, good }: { icon: React.ComponentType<{ className?: string; strokeWidth?: number }>; label: string; value: string; good?: boolean }) {
  return (
    <li className="flex items-center justify-between gap-2">
      <span className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-4" strokeWidth={1.75} />
        {label}
      </span>
      <span className={good === undefined ? 'font-medium' : good ? 'font-medium text-success' : 'font-medium text-warning'}>{value}</span>
    </li>
  );
}

function Info({ label, value, ltr }: { label: string; value: string; ltr?: boolean }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={ltr ? 'ltr-nums mt-0.5 font-medium' : 'mt-0.5 font-medium'}>{value}</p>
    </div>
  );
}
