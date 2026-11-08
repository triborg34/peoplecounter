import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import {
  Cog6ToothIcon,
  ShieldCheckIcon,
  ServerIcon,
  ClockIcon,
  CheckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface AuditEntry {
  id: number;
  ts: string;
  username: string;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  details: string;
  ip_address: string;
}

interface SystemStatus {
  status: string;
  version: string;
  engine_running: boolean;
  detector_available: boolean;
}

export function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'system' | 'security' | 'audit'>('system');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getSystemStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch system status:', err);
    }
  }, []);

  const fetchAudit = useCallback(async () => {
    setLoadingAudit(true);
    try {
      const data = await api.getAuditLog({ limit: 200 });
      setAudit(data);
    } catch (err) {
      console.error('Failed to fetch audit log:', err);
    } finally {
      setLoadingAudit(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (activeTab === 'audit') fetchAudit();
  }, [activeTab, fetchAudit]);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setError('رمزهای عبور مطابقت ندارند');
      return;
    }
    if (passwordForm.new_password.length < 8) {
      setError('رمز عبور باید حداقل ۸ کاراکتر باشد');
      return;
    }
    setSaving(true);
    try {
      await api.changePassword(passwordForm.current_password, passwordForm.new_password);
      setSuccess('رمز عبور با موفقیت تغییر کرد');
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در تغییر رمز عبور');
    } finally {
      setSaving(false);
    }
  };

  const tabs = [
    { id: 'system', label: 'وضعیت سیستم', icon: ServerIcon },
    { id: 'security', label: 'امنیت', icon: ShieldCheckIcon },
    { id: 'audit', label: 'گزارش فعالیت', icon: ClockIcon },
  ] as const;

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">تنظیمات سیستم</h1>
        <p className="text-gray-500 mt-1">
          وضعیت سرویس، امنیت حساب و گزارش فعالیت‌ها
        </p>
      </div>

      <div className="card">
        <div className="border-b border-gray-200">
          <nav className="flex gap-1 px-4" aria-label="تنظیمات">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setError(null);
                  setSuccess(null);
                }}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-t-lg transition-colors -mb-px border-b-2 ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
                role="tab"
                aria-selected={activeTab === tab.id}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="card-body">
          {error && (
            <div className="mb-5 p-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-center gap-2">
              <XMarkIcon className="w-5 h-5" />
              {error}
            </div>
          )}
          {success && (
            <div className="mb-5 p-3 bg-green-50 text-green-700 rounded-lg text-sm flex items-center gap-2">
              <CheckIcon className="w-5 h-5" />
              {success}
            </div>
          )}

          {activeTab === 'system' && (
            <div className="space-y-5 max-w-2xl">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <InfoRow label="وضعیت سرویس" value={status?.status === 'ok' ? 'فعال' : 'نامشخص'} ok={status?.status === 'ok'} />
                <InfoRow label="نسخه" value={status?.version || '—'} />
                <InfoRow label="موتور تشخیص" value={status?.engine_running ? 'در حال اجرا' : 'متوقف'} ok={!!status?.engine_running} />
                <InfoRow label="مدل YOLO" value={status?.detector_available ? 'بارگذاری شده' : 'در دسترس نیست'} ok={!!status?.detector_available} />
                <InfoRow label="کاربر جاری" value={user?.username || '—'} />
                <InfoRow label="نقش" value={roleLabel(user?.role)} />
              </div>

              {status && !status.detector_available && (
                <div className="p-4 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
                  مدل تشخیص بارگذاری نشده است. فایل مدل را در پوشه
                  <span className="font-mono mx-1">data/models/</span>
                  قرار دهید و سرویس را دوباره راه‌اندازی کنید تا شمارش شروع شود.
                </div>
              )}

              <div className="pt-4 border-t border-gray-100">
                <button onClick={fetchStatus} className="btn-secondary">
                  به‌روزرسانی وضعیت
                </button>
              </div>

              <p className="text-xs text-gray-400 flex items-center gap-1">
                <Cog6ToothIcon className="w-4 h-4" />
                سایر تنظیمات از طریق فایل .env در سمت سرور قابل پیکربندی است.
              </p>
            </div>
          )}

          {activeTab === 'security' && (
            <form onSubmit={handleChangePassword} className="space-y-5 max-w-md">
              <div>
                <label htmlFor="current_password" className="label-field">رمز عبور فعلی</label>
                <input
                  id="current_password"
                  type="password"
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                  className="input-field"
                  autoComplete="current-password"
                  required
                />
              </div>
              <div>
                <label htmlFor="new_password" className="label-field">رمز عبور جدید</label>
                <input
                  id="new_password"
                  type="password"
                  value={passwordForm.new_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                  className="input-field"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
                <p className="text-xs text-gray-500 mt-1">حداقل ۸ کاراکتر</p>
              </div>
              <div>
                <label htmlFor="confirm_password" className="label-field">تکرار رمز عبور جدید</label>
                <input
                  id="confirm_password"
                  type="password"
                  value={passwordForm.confirm_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                  className="input-field"
                  autoComplete="new-password"
                  required
                />
              </div>
              <div className="flex justify-end pt-5 border-t border-gray-100">
                <button type="submit" disabled={saving} className="btn-primary">
                  {saving ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <ShieldCheckIcon className="w-5 h-5" />
                      تغییر رمز عبور
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'audit' && (
            <div>
              {user?.role !== 'admin' ? (
                <div className="empty-state h-40">
                  <ShieldCheckIcon className="empty-state-icon w-12 h-12" />
                  <p className="empty-state-description">این بخش فقط برای مدیران قابل مشاهده است</p>
                </div>
              ) : loadingAudit ? (
                <div className="flex items-center justify-center h-40">
                  <svg className="spinner-lg" />
                </div>
              ) : audit.length === 0 ? (
                <div className="empty-state h-40">
                  <ClockIcon className="empty-state-icon w-12 h-12" />
                  <p className="empty-state-description">هیچ فعالیتی ثبت نشده است</p>
                </div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>زمان</th>
                        <th>کاربر</th>
                        <th>عملیات</th>
                        <th>موجودیت</th>
                        <th>جزئیات</th>
                        <th>IP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.map((entry) => (
                        <tr key={entry.id} className="hover:bg-gray-50">
                          <td className="text-sm text-gray-500 whitespace-nowrap">{entry.ts}</td>
                          <td className="font-medium text-gray-900">{entry.username || '—'}</td>
                          <td><span className="badge badge-info text-xs">{entry.action}</span></td>
                          <td className="text-sm text-gray-600">
                            {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ''}` : '—'}
                          </td>
                          <td className="text-sm text-gray-600 max-w-xs truncate">{entry.details || '—'}</td>
                          <td className="text-xs text-gray-400 font-mono">{entry.ip_address || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function roleLabel(role?: string) {
  if (role === 'admin') return 'مدیر';
  if (role === 'operator') return 'اپراتور';
  if (role === 'viewer') return 'بیننده';
  return role || '—';
}

function InfoRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <span className="text-sm text-gray-500">{label}</span>
      <span
        className={`text-sm font-medium flex items-center gap-1.5 ${
          ok === undefined ? 'text-gray-900' : ok ? 'text-green-600' : 'text-red-600'
        }`}
      >
        {ok !== undefined && <span className={`w-2 h-2 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />}
        {value}
      </span>
    </div>
  );
}
