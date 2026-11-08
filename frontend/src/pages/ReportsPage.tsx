import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import { type Camera, type ReportSummary } from '../api/types';
import {
  DocumentArrowDownIcon,
  DocumentTextIcon,
  UsersIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { format, subDays } from 'date-fns';
import jalaliMoment from 'jalali-moment';

type ExportFormat = 'csv' | 'excel' | 'pdf';

export function ReportsPage() {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState({
    camera_id: '',
    start_date: format(subDays(new Date(), 30), 'yyyy-MM-dd'),
    end_date: format(new Date(), 'yyyy-MM-dd'),
    interval: 'day',
  });

  const buildParams = useCallback(() => {
    const params: Record<string, unknown> = { interval: filters.interval };
    // Backend expects ISO datetimes for start/end.
    if (filters.start_date) params.start = `${filters.start_date}T00:00:00`;
    if (filters.end_date) params.end = `${filters.end_date}T23:59:59`;
    if (filters.camera_id) params.camera_id = [parseInt(filters.camera_id)];
    return params;
  }, [filters]);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getReportSummary(buildParams());
      setSummary(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در بارگذاری گزارش');
      console.error('Failed to fetch report summary:', err);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  const fetchCameras = useCallback(async () => {
    try {
      const res = await api.getCameras({ size: 100 });
      setCameras(res.items);
    } catch (err) {
      console.error('Failed to fetch cameras:', err);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleExport = async (fmt: ExportFormat) => {
    setExporting(fmt);
    try {
      const params = buildParams();
      const blob = await api.exportReport({ ...params, format: fmt } as any);
      const ext = fmt === 'excel' ? 'xlsx' : fmt;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report-${filters.start_date}-to-${filters.end_date}.${ext}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در تولید گزارش');
    } finally {
      setExporting(null);
    }
  };

  const totals = summary?.totals || { in: 0, out: 0, total: 0, events: 0 };
  const timeseries = (summary?.timeseries || []) as Array<{ bucket: string; in: number; out: number; total: number }>;
  const byCamera = (summary?.by_camera || []) as Array<{ camera_id: number; camera_name: string; in: number; out: number; total: number }>;
  const peakHours = (summary?.peak_hours || []) as Array<{ hour: number; label: string; count: number }>;

  const maxSeries = Math.max(1, ...timeseries.map((p) => p.total));

  const fmtDate = (d: string) => {
    try {
      return jalaliMoment(d).format('jYYYY/jMM/jDD');
    } catch {
      return d;
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">گزارش‌ها</h1>
          <p className="text-gray-500 mt-1">مشاهده آمار شمارش افراد و خروجی اکسل / PDF / CSV</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => handleExport('excel')} disabled={!!exporting} className="btn-secondary">
            <DocumentArrowDownIcon className="w-5 h-5 ml-2" />
            {exporting === 'excel' ? 'در حال تولید...' : 'Excel'}
          </button>
          <button onClick={() => handleExport('pdf')} disabled={!!exporting} className="btn-secondary">
            <DocumentArrowDownIcon className="w-5 h-5 ml-2" />
            {exporting === 'pdf' ? 'در حال تولید...' : 'PDF'}
          </button>
          <button onClick={() => handleExport('csv')} disabled={!!exporting} className="btn-primary">
            <DocumentArrowDownIcon className="w-5 h-5 ml-2" />
            {exporting === 'csv' ? 'در حال تولید...' : 'CSV'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="card-body">
          <form className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <label htmlFor="camera" className="label-field">دوربین</label>
              <select
                id="camera"
                value={filters.camera_id}
                onChange={(e) => handleFilterChange('camera_id', e.target.value)}
                className="input-field"
              >
                <option value="">همه دوربین‌ها</option>
                {cameras.map((cam) => (
                  <option key={cam.id} value={cam.id}>{cam.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="start_date" className="label-field">از تاریخ</label>
              <input
                id="start_date"
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="input-field"
                max={filters.end_date}
              />
            </div>

            <div>
              <label htmlFor="end_date" className="label-field">تا تاریخ</label>
              <input
                id="end_date"
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="input-field"
                min={filters.start_date}
                max={format(new Date(), 'yyyy-MM-dd')}
              />
            </div>

            <div>
              <label htmlFor="interval" className="label-field">بازه تجمیع</label>
              <select
                id="interval"
                value={filters.interval}
                onChange={(e) => handleFilterChange('interval', e.target.value)}
                className="input-field"
              >
                <option value="hour">ساعتی</option>
                <option value="day">روزانه</option>
                <option value="week">هفتگی</option>
                <option value="month">ماهانه</option>
              </select>
            </div>

            <div className="flex items-end">
              <button type="button" onClick={fetchSummary} className="btn-primary w-full">
                <ChartBarIcon className="w-5 h-5 ml-2" />
                اعمال فیلتر
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="کل ورود" value={totals.in} icon={ArrowTrendingUpIcon} color="green" />
        <StatCard title="کل خروج" value={totals.out} icon={ArrowTrendingDownIcon} color="orange" />
        <StatCard title="مجموع شمارش" value={totals.total} icon={UsersIcon} color="blue" />
        <StatCard title="تعداد رویداد" value={totals.events} icon={DocumentTextIcon} color="purple" />
      </div>

      {/* Timeseries chart */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">روند شمارش در زمان</h2>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <svg className="spinner-lg" />
            </div>
          ) : timeseries.length === 0 ? (
            <div className="empty-state h-48">
              <ChartBarIcon className="empty-state-icon w-12 h-12" />
              <p className="empty-state-description">داده‌ای در بازه انتخابی وجود ندارد</p>
            </div>
          ) : (
            <BarChart data={timeseries} maxValue={maxSeries} />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By camera */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">آمار به تفکیک دوربین</h2>
          </div>
          <div className="card-body p-0">
            {byCamera.length === 0 ? (
              <div className="empty-state h-40">
                <p className="empty-state-description">داده‌ای موجود نیست</p>
              </div>
            ) : (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>دوربین</th>
                      <th>ورود</th>
                      <th>خروج</th>
                      <th>مجموع</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byCamera.map((row) => (
                      <tr key={row.camera_id} className="hover:bg-gray-50">
                        <td className="font-medium text-gray-900">{row.camera_name || `#${row.camera_id}`}</td>
                        <td className="text-green-600 persian-numbers">{row.in}</td>
                        <td className="text-orange-600 persian-numbers">{row.out}</td>
                        <td className="font-bold persian-numbers">{row.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Peak hours */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">ساعات پرترافیک</h2>
          </div>
          <div className="card-body">
            {peakHours.length === 0 ? (
              <div className="empty-state h-40">
                <p className="empty-state-description">داده‌ای موجود نیست</p>
              </div>
            ) : (
              <div className="space-y-2">
                {peakHours.slice(0, 8).map((row) => {
                  const maxCount = Math.max(...peakHours.map((p) => p.count), 1);
                  return (
                    <div key={row.hour} className="flex items-center gap-3">
                      <span className="w-14 text-sm text-gray-500 font-mono">{row.label}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div
                          className="bg-blue-500 h-full rounded-full transition-all"
                          style={{ width: `${(row.count / maxCount) * 100}%` }}
                        />
                      </div>
                      <span className="w-12 text-sm text-gray-700 text-left persian-numbers">{row.count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-400 text-center">
        بازه: {fmtDate(filters.start_date)} تا {fmtDate(filters.end_date)}
      </p>
    </div>
  );
}

// Simple dependency-free bar chart so we don't rely on a charting lib here.
function BarChart({ data, maxValue }: { data: Array<{ bucket: string; in: number; out: number; total: number }>; maxValue: number }) {
  return (
    <div className="flex items-end gap-1 h-56 overflow-x-auto pb-6 relative">
      {data.map((point, i) => (
        <div key={i} className="flex flex-col items-center justify-end flex-shrink-0 group" style={{ minWidth: 28 }}>
          <div className="relative w-full flex items-end justify-center gap-0.5" style={{ height: 180 }}>
            <div
              className="w-2.5 bg-green-500 rounded-t"
              style={{ height: `${(point.in / maxValue) * 100}%` }}
              title={`ورود: ${point.in}`}
            />
            <div
              className="w-2.5 bg-orange-500 rounded-t"
              style={{ height: `${(point.out / maxValue) * 100}%` }}
              title={`خروج: ${point.out}`}
            />
            <div className="hidden group-hover:block absolute -top-6 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
              {point.in} / {point.out}
            </div>
          </div>
          <span className="text-[10px] text-gray-400 mt-1 rotate-45 origin-top-left whitespace-nowrap">
            {point.bucket}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: 'blue' | 'green' | 'orange' | 'purple' | 'red';
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
        </div>
        <div className={`${colors[color]} p-3 rounded-xl`}>
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
