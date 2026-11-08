import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import { type Camera, type Report, type ReportGenerate, type ReportStats } from '../api/types';
import {
  DocumentArrowDownIcon,
  DocumentTextIcon,
  XMarkIcon,
  TrashIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';
import { format, parseISO, subDays } from 'date-fns';
import jalaliMoment from 'jalali-moment';

export function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [stats, setStats] = useState<ReportStats | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Filters
  const [filters, setFilters] = useState({
    camera_id: '',
    zone_id: '',
    start_date: format(subDays(new Date(), 30), 'yyyy-MM-dd'),
    end_date: format(new Date(), 'yyyy-MM-dd'),
    format: 'pdf' as 'pdf' | 'excel',
  });

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, size: 20 };
      if (filters.camera_id) params.camera_id = parseInt(filters.camera_id);
      if (filters.zone_id) params.zone_id = parseInt(filters.zone_id);
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      
      const res = await api.getReports(params);
      setReports(res.items);
      setTotalPages(res.pages);
      setTotalItems(res.total);
    } catch (err: any) {
      console.error('Failed to fetch reports:', err);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  const fetchStats = useCallback(async () => {
    try {
      const params: any = {};
      if (filters.camera_id) params.camera_id = parseInt(filters.camera_id);
      if (filters.zone_id) params.zone_id = parseInt(filters.zone_id);
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      
      const data = await api.getReportStats(params);
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch report stats:', err);
    }
  }, [filters]);

  const fetchCameras = useCallback(async () => {
    try {
      const res = await api.getCameras({ size: 100 });
      setCameras(res.items);
    } catch (err) {
      console.error('Failed to fetch cameras:', err);
    }
  }, []);

  useEffect(() => {
    fetchReports();
    fetchStats();
    fetchCameras();
  }, [fetchReports, fetchStats, fetchCameras]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleGenerateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const params: ReportGenerate = {
        camera_id: filters.camera_id ? parseInt(filters.camera_id) : undefined,
        zone_id: filters.zone_id ? parseInt(filters.zone_id) : undefined,
        start_date: filters.start_date,
        end_date: filters.end_date,
        format: filters.format,
      };
      const blob = await api.generateReport(params);
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report-${filters.start_date}-to-${filters.end_date}.${filters.format === 'pdf' ? 'pdf' : 'xlsx'}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      setShowGenerateModal(false);
      fetchReports();
      fetchStats();
    } catch (err: any) {
      console.error('Failed to generate report:', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleDeleteReport = async (report: Report) => {
    if (!window.confirm(`آیا از حذف گزارش "${report.name}" مطمئن هستید؟`)) return;
    try {
      // Note: API doesn't have delete report endpoint yet, would need to be added
      setReports((prev) => prev.filter((r) => r.id !== report.id));
    } catch (err) {
      console.error('Failed to delete report:', err);
    }
  };

  const handleViewReport = (report: Report) => {
    // Open report file in new tab
    window.open(`/api/v1/reports/${report.id}/download`, '_blank');
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = parseISO(dateStr);
      return jalaliMoment(date).format('jYYYY/jMM/jDD HH:mm');
    } catch {
      return dateStr;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' بایت';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' کیلوبایت';
    return (bytes / (1024 * 1024)).toFixed(1) + ' مگابایت';
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">گزارش‌ها</h1>
          <p className="text-gray-500 mt-1">مشاهده و تولید گزارش‌های شمارش افراد</p>
        </div>
        <button onClick={() => setShowGenerateModal(true)} className="btn-primary">
          <DocumentArrowDownIcon className="w-5 h-5 ml-2" />
          تولید گزارش
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="کل گزارش‌ها" value={stats.total_reports} icon={DocumentTextIcon} color="blue" />
          <StatCard title="حجم کل" value={formatFileSize(stats.total_size)} icon={DocumentArrowDownIcon} color="green" />
          <StatCard title="PDF" value={stats.by_format?.pdf || 0} icon={DocumentTextIcon} color="red" />
          <StatCard title="Excel" value={stats.by_format?.excel || 0} icon={DocumentArrowDownIcon} color="green" />
        </div>
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
              <label htmlFor="format" className="label-field">فرمت</label>
              <select
                id="format"
                value={filters.format}
                onChange={(e) => handleFilterChange('format', e.target.value)}
                className="input-field"
              >
                <option value="pdf">PDF</option>
                <option value="excel">Excel</option>
              </select>
            </div>

            <div className="flex items-end">
              <button type="button" onClick={handleGenerateReport} className="btn-primary w-full">
                <DocumentArrowDownIcon className="w-5 h-5 ml-2" />
                تولید
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Reports Table */}
      <div className="card">
        <div className="card-body p-0">
          {loading && reports.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <svg className="spinner-lg" />
            </div>
          ) : reports.length === 0 ? (
            <div className="empty-state h-64">
              <DocumentTextIcon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">هیچ گزارشی یافت نشد</h3>
              <p className="empty-state-description">با تغییر فیلترها جستجو کنید یا گزارش جدیدی تولید کنید</p>
            </div>
          ) : (
            <>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>نام گزارش</th>
                      <th>دوربین</th>
                      <th>بازه زمانی</th>
                      <th>فرمت</th>
                      <th>حجم</th>
                      <th>تولید شده</th>
                      <th>توسط</th>
                      <th className="text-left">عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((report) => (
                      <tr key={report.id} className="hover:bg-gray-50">
                        <td className="font-medium text-gray-900">{report.name}</td>
                        <td>{report.camera_id ? `دوربین #${report.camera_id}` : 'همه دوربین‌ها'}</td>
                        <td>
                          <div className="text-sm">
                            <p>{formatDate(report.start_date)}</p>
                            <p className="text-gray-500">{formatDate(report.end_date)}</p>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${report.format === 'pdf' ? 'badge-danger' : 'badge-success'}`}>
                            {report.format.toUpperCase()}
                          </span>
                        </td>
                        <td className="font-mono text-sm">{formatFileSize(report.file_size)}</td>
                        <td className="text-sm">{formatDate(report.generated_at)}</td>
                        <td className="text-sm text-gray-500">کاربر #{report.generated_by}</td>
                        <td>
                          <div className="flex items-center gap-2 text-left">
                            <button
                              onClick={() => handleViewReport(report)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                              aria-label="مشاهده"
                            >
                              <EyeIcon className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => handleDeleteReport(report)}
                              className="p-2 text-red-500 hover:text-red-700 hover:bg-red-100 rounded-lg transition-colors"
                              aria-label="حذف"
                            >
                              <TrashIcon className="w-5 h-5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                  <p className="text-sm text-gray-500">
                    نمایش {((page - 1) * 20) + 1} تا {Math.min(page * 20, totalItems)} از {totalItems}
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="btn-outline btn-sm"
                    >
                      قبلی
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="btn-outline btn-sm"
                    >
                      بعدی
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Generate Report Modal */}
      {showGenerateModal && (
        <div className="modal-overlay" onClick={() => setShowGenerateModal(false)} role="dialog" aria-modal="true" aria-labelledby="generate-modal-title">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="card-header flex items-center justify-between">
              <h2 id="generate-modal-title" className="text-lg font-semibold text-gray-900">تولید گزارش جدید</h2>
              <button onClick={() => setShowGenerateModal(false)} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleGenerateReport} className="card-body space-y-5">
              <div>
                <label htmlFor="gen-camera" className="label-field">دوربین</label>
                <select
                  id="gen-camera"
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="gen-start" className="label-field">از تاریخ</label>
                  <input
                    id="gen-start"
                    type="date"
                    value={filters.start_date}
                    onChange={(e) => handleFilterChange('start_date', e.target.value)}
                    className="input-field"
                    max={filters.end_date}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="gen-end" className="label-field">تا تاریخ</label>
                  <input
                    id="gen-end"
                    type="date"
                    value={filters.end_date}
                    onChange={(e) => handleFilterChange('end_date', e.target.value)}
                    className="input-field"
                    min={filters.start_date}
                    max={format(new Date(), 'yyyy-MM-dd')}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="label-field">فرمت گزارش</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="format"
                      value="pdf"
                      checked={filters.format === 'pdf'}
                      onChange={(e) => handleFilterChange('format', e.target.value)}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">PDF</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="format"
                      value="excel"
                      checked={filters.format === 'excel'}
                      onChange={(e) => handleFilterChange('format', e.target.value)}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Excel (XLSX)</span>
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 border-t border-gray-100 pt-5">
                <button type="button" onClick={() => setShowGenerateModal(false)} className="btn-secondary">
                  انصراف
                </button>
                <button type="submit" disabled={generating} className="btn-primary">
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال تولید...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <DocumentArrowDownIcon className="w-5 h-5" />
                      تولید و دانلود
                    </span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// Stat Card Component
function StatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: number | string;
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
          <p className="text-3xl font-bold text-gray-900 mt-1 persian-numbers">{value}</p>
        </div>
        <div className={`${colors[color]} p-3 rounded-xl`}>
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}