import { useCallback, useEffect, useState } from 'react';
import { BarChart3, Download, FileSpreadsheet, FileText, Table2 } from 'lucide-react';
import api from '@/api/client';
import { type Camera, type ReportSummary } from '@/api/types';
import { faNumber } from '@/lib/utils';
import { toJalali, JALALI_MONTHS } from '@/lib/jalali';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert } from '@/components/ui/alert';
import { EmptyState } from '@/components/ui/empty-state';
import { Field } from '@/components/ui/input';
import { DatePicker } from '@/components/ui/date-picker';
import { BarChart, LineChart, type Point } from '@/components/ui/chart';
import { Stat } from '@/components/ui/stat';

type ExportFormat = 'csv' | 'excel' | 'pdf';

const isoDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** برچسب کوتاه شمسی برای یک سطل زمانی ISO («۲۵ شهریور» یا «۲۵ شه ۱۴»). */
function bucketLabel(bucket: string, interval: string): string {
  const d = new Date(bucket);
  if (isNaN(d.getTime())) return bucket;
  const { jm, jd } = toJalali(d);
  if (interval === 'hour') return `${faNumber(d.getHours())}:۰۰`;
  if (interval === 'month') return JALALI_MONTHS[jm - 1];
  return `${faNumber(jd)} ${JALALI_MONTHS[jm - 1].slice(0, 2)}`;
}

const INTERVALS = [
  { value: 'hour', label: 'ساعتی' },
  { value: 'day', label: 'روزانه' },
  { value: 'week', label: 'هفتگی' },
  { value: 'month', label: 'ماهانه' },
];

export function ReportsPage() {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState('');

  const monthAgo = new Date(Date.now() - 30 * 864e5);
  const [cameraId, setCameraId] = useState('');
  const [start, setStart] = useState<Date | null>(monthAgo);
  const [end, setEnd] = useState<Date | null>(new Date());
  const [interval, setInterval_] = useState('day');

  const buildParams = useCallback((): Record<string, unknown> => {
    const params: Record<string, unknown> = { interval };
    if (start) params.start = `${isoDate(start)}T00:00:00`;
    if (end) params.end = `${isoDate(end)}T23:59:59`;
    if (cameraId) params.camera_id = [parseInt(cameraId)];
    return params;
  }, [interval, start, end, cameraId]);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setSummary(await api.getReportSummary(buildParams() as any));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در بارگذاری گزارش');
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => {
    api.getCameras({ size: 100 }).then((r) => setCameras(r.items)).catch(() => undefined);
  }, []);
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  async function handleExport(fmt: ExportFormat) {
    setExporting(fmt);
    try {
      const blob = await api.exportReport({ ...buildParams(), format: fmt } as any);
      const ext = fmt === 'excel' ? 'xlsx' : fmt;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${start ? isoDate(start) : 'start'}-to-${end ? isoDate(end) : 'now'}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در تولید خروجی');
    } finally {
      setExporting(null);
    }
  }

  const totals = (summary?.totals ?? {}) as Record<string, number>;
  const timeseries = (summary?.timeseries ?? []) as Array<{ bucket: string; in: number; out: number; total: number }>;
  const byCamera = (summary?.by_camera ?? []) as Array<{ camera_id: number; camera_name: string; in: number; out: number; total: number }>;
  const peakHours = (summary?.peak_hours ?? []) as Array<{ hour: number; label: string; count: number }>;

  const seriesIn: Point[] = timeseries.map((p) => ({ label: bucketLabel(p.bucket, interval), value: p.in || 0 }));
  const seriesOut: Point[] = timeseries.map((p) => ({ label: bucketLabel(p.bucket, interval), value: p.out || 0 }));
  const maxPeak = Math.max(1, ...peakHours.map((p) => p.count));

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-lg font-bold">گزارش‌ها</h1>
          <p className="text-sm text-muted-foreground">آمار شمارش با نمودار و خروجی اکسل، PDF و CSV</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={!!exporting} onClick={() => handleExport('excel')}>
            <FileSpreadsheet className="size-4" />
            {exporting === 'excel' ? 'در حال تولید…' : 'اکسل'}
          </Button>
          <Button variant="outline" size="sm" disabled={!!exporting} onClick={() => handleExport('pdf')}>
            <FileText className="size-4" />
            {exporting === 'pdf' ? 'در حال تولید…' : 'PDF'}
          </Button>
          <Button size="sm" disabled={!!exporting} onClick={() => handleExport('csv')}>
            <Download className="size-4" />
            {exporting === 'csv' ? 'در حال تولید…' : 'CSV'}
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      {/* فیلترها */}
      <Card>
        <CardContent className="grid grid-cols-1 gap-4 pt-5 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="دوربین" htmlFor="rep-camera">
            <select
              id="rep-camera"
              value={cameraId}
              onChange={(e) => setCameraId(e.target.value)}
              className="h-10 w-full rounded-field border-line-field border-input bg-field px-3 text-sm shadow-field focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              <option value="">همه دوربین‌ها</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="از تاریخ">
            <DatePicker value={start} onChange={setStart} max={end ?? undefined} />
          </Field>
          <Field label="تا تاریخ">
            <DatePicker value={end} onChange={setEnd} min={start ?? undefined} max={new Date()} />
          </Field>
          <Field label="بازه تجمیع" htmlFor="rep-interval">
            <select
              id="rep-interval"
              value={interval}
              onChange={(e) => setInterval_(e.target.value)}
              className="h-10 w-full rounded-field border-line-field border-input bg-field px-3 text-sm shadow-field focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              {INTERVALS.map((i) => (
                <option key={i.value} value={i.value}>
                  {i.label}
                </option>
              ))}
            </select>
          </Field>
        </CardContent>
      </Card>

      {/* جمع کل */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="کل ورود" value={faNumber(totals.in ?? 0)} />
        <Stat label="کل خروج" value={faNumber(totals.out ?? 0)} />
        <Stat label="مجموع شمارش" value={faNumber(totals.total ?? 0)} />
        <Stat label="تعداد رویداد" value={faNumber(totals.events ?? 0)} />
      </div>

      {/* روند زمانی */}
      <Card>
        <CardHeader>
          <CardTitle>روند شمارش در زمان</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-48 animate-pulse rounded-field bg-secondary/60" />
          ) : seriesIn.length === 0 ? (
            <EmptyState icon={BarChart3} title="داده‌ای در این بازه نیست" description="بازه‌ی زمانی یا دوربین دیگری را امتحان کنید." />
          ) : (
            <div className="space-y-6">
              <div>
                <p className="mb-1 text-xs font-medium text-success">ورود</p>
                <LineChart data={seriesIn} height={170} />
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-warning">خروج</p>
                <BarChart data={seriesOut} height={170} />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* تفکیک دوربین */}
        <Card>
          <CardHeader>
            <CardTitle>به تفکیک دوربین</CardTitle>
          </CardHeader>
          <CardContent>
            {byCamera.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">داده‌ای موجود نیست</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-line border-b border-border text-xs text-muted-foreground">
                    <th className="pb-2 text-start font-medium">دوربین</th>
                    <th className="pb-2 text-start font-medium">ورود</th>
                    <th className="pb-2 text-start font-medium">خروج</th>
                    <th className="pb-2 text-start font-medium">مجموع</th>
                  </tr>
                </thead>
                <tbody>
                  {byCamera.map((row) => (
                    <tr key={row.camera_id} className="border-line border-b border-border/50 last:border-0">
                      <td className="py-2 font-medium">{row.camera_name || `#${row.camera_id}`}</td>
                      <td className="py-2 tabular-nums text-success">{faNumber(row.in)}</td>
                      <td className="py-2 tabular-nums text-warning">{faNumber(row.out)}</td>
                      <td className="py-2 font-bold tabular-nums">{faNumber(row.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        {/* ساعات پرترافیک */}
        <Card>
          <CardHeader>
            <CardTitle>ساعات پرترافیک</CardTitle>
          </CardHeader>
          <CardContent>
            {peakHours.length === 0 ? (
              <EmptyState icon={Table2} title="داده‌ای موجود نیست" />
            ) : (
              <div className="space-y-2.5">
                {peakHours.slice(0, 8).map((row) => (
                  <div key={row.hour} className="flex items-center gap-3">
                    <span className="ltr-nums w-14 shrink-0 text-xs tabular-nums text-muted-foreground">{row.label}</span>
                    <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-secondary">
                      <div className="h-full rounded-full bg-brand transition-all duration-(--motion) ease-motion" style={{ width: `${(row.count / maxPeak) * 100}%` }} />
                    </div>
                    <span className="w-12 shrink-0 text-end text-xs tabular-nums">{faNumber(row.count)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
