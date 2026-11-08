import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import {
  Cog6ToothIcon,
  ShieldCheckIcon,
  KeyIcon,
  ServerIcon,
  ChartBarIcon,
  ArrowPathIcon,
  XMarkIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

export function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'general' | 'detection' | 'counting' | 'api' | 'security'>('general');

  // Form states
  const [generalForm, setGeneralForm] = useState({
    app_name: '',
    log_level: 'INFO',
  });

  const [detectionForm, setDetectionForm] = useState({
    model_name: 'yolov8n.pt',
    confidence: 0.4,
    iou: 0.7,
    imgsz: 640,
    device: 'auto',
    batch_size: 4,
    batch_window_ms: 40,
  });

  const [countingForm, setCountingForm] = useState({
    track_point: 'bottom',
    counting_cooldown_s: 1.5,
    counting_min_displacement: 0.015,
  });

  const [apiForm, setApiForm] = useState({
    api_enabled: false,
    api_host: '127.0.0.1',
    api_port: 8000,
    cors_origins: '',
    rate_limit_login_per_minute: 10,
  });

  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const fetchSettings = useCallback(async () => {
    try {
      const data = await api.getSettings();
      setGeneralForm({
        app_name: data.app_name,
        log_level: data.log_level,
      });
      setDetectionForm({
        model_name: data.detection_model,
        confidence: data.detection_confidence,
        iou: data.detection_iou,
        imgsz: data.detection_imgsz,
        device: data.detection_device,
        batch_size: 4,
        batch_window_ms: 40,
      });
      setCountingForm({
        track_point: data.track_point,
        counting_cooldown_s: data.counting_cooldown,
        counting_min_displacement: data.counting_min_displacement,
      });
      setApiForm({
        api_enabled: data.api_enabled,
        api_host: data.api_host,
        api_port: data.api_port,
        cors_origins: data.cors_origins.join(','),
        rate_limit_login_per_minute: data.rate_limit_login_per_minute,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در بارگذاری تنظیمات');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = async (section: string) => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      let data: any = {};
      
      switch (section) {
        case 'general':
          data = { ...generalForm };
          break;
        case 'detection':
          data = { ...detectionForm };
          break;
        case 'counting':
          data = { ...countingForm };
          break;
        case 'api':
          data = {
            ...apiForm,
            cors_origins: apiForm.cors_origins.split(',').map((s: string) => s.trim()).filter(Boolean),
          };
          break;
      }

      await api.updateSettings(data);
      setSuccess(`${getSectionTitle(section)} با موفقیت ذخیره شد`);
      fetchSettings();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در ذخیره تنظیمات');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setError('رمزهای عبور مطابقت ندارند');
      return;
    }
    if (passwordForm.new_password.length < 6) {
      setError('رمز عبور باید حداقل ۶ کاراکتر باشد');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);
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

  const getSectionTitle = (section: string) => {
    const titles: Record<string, string> = {
      general: 'تنظیمات عمومی',
      detection: 'تنظیمات تشخیص',
      counting: 'تنظیمات شمارش',
      api: 'تنظیمات API',
      security: 'تنظیمات امنیتی',
    };
    return titles[section] || section;
  };

  const tabs = [
    { id: 'general', label: 'عمومی', icon: Cog6ToothIcon },
    { id: 'detection', label: 'تشخیص', icon: ChartBarIcon },
    { id: 'counting', label: 'شمارش', icon: ServerIcon },
    { id: 'api', label: 'API', icon: ArrowPathIcon },
    { id: 'security', label: 'امنیت', icon: ShieldCheckIcon },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <svg className="spinner-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">تنظیمات سیستم</h1>
        <p className="text-gray-500 mt-1">پیکربندی پارامترهای سیستم شمارش افراد</p>
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-gray-200">
          <nav className="flex gap-1 px-4" aria-label="تنظیمات">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
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

          {/* General Tab */}
          {activeTab === 'general' && (
            <form className="space-y-5 max-w-2xl">
              <div>
                <label htmlFor="app_name" className="label-field">نام برنامه</label>
                <input
                  id="app_name"
                  type="text"
                  value={generalForm.app_name}
                  onChange={(e) => setGeneralForm({ ...generalForm, app_name: e.target.value })}
                  className="input-field"
                  placeholder="People Counter"
                />
              </div>

              <div>
                <label htmlFor="log_level" className="label-field">سطح لاگ</label>
                <select
                  id="log_level"
                  value={generalForm.log_level}
                  onChange={(e) => setGeneralForm({ ...generalForm, log_level: e.target.value })}
                  className="input-field"
                >
                  <option value="DEBUG">Debug</option>
                  <option value="INFO">Info</option>
                  <option value="WARNING">Warning</option>
                  <option value="ERROR">Error</option>
                </select>
              </div>

              <div className="flex justify-end pt-5 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => handleSave('general')}
                  disabled={saving}
                  className="btn-primary"
                >
                  {saving ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <CheckIcon className="w-5 h-5" />
                      ذخیره تنظیمات عمومی
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Detection Tab */}
          {activeTab === 'detection' && (
            <form className="space-y-5 max-w-2xl">
              <div>
                <label htmlFor="model_name" className="label-field">مدل تشخیص</label>
                <input
                  id="model_name"
                  type="text"
                  value={detectionForm.model_name}
                  onChange={(e) => setDetectionForm({ ...detectionForm, model_name: e.target.value })}
                  className="input-field"
                  placeholder="yolov8n.pt"
                />
                <p className="text-xs text-gray-500 mt-1">نام فایل مدل YOLO (باید در پوشه models وجود داشته باشد)</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="confidence" className="label-field">
                    حد اعتماد: <span className="font-mono text-blue-600">{Math.round(detectionForm.confidence * 100)}%</span>
                  </label>
                  <input
                    id="confidence"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={detectionForm.confidence}
                    onChange={(e) => setDetectionForm({ ...detectionForm, confidence: parseFloat(e.target.value) })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>
                <div>
                  <label htmlFor="iou" className="label-field">
                    آستانه IoU: <span className="font-mono text-blue-600">{Math.round(detectionForm.iou * 100)}%</span>
                  </label>
                  <input
                    id="iou"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={detectionForm.iou}
                    onChange={(e) => setDetectionForm({ ...detectionForm, iou: parseFloat(e.target.value) })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label htmlFor="imgsz" className="label-field">اندازه تصویر</label>
                  <input
                    id="imgsz"
                    type="number"
                    value={detectionForm.imgsz}
                    onChange={(e) => setDetectionForm({ ...detectionForm, imgsz: parseInt(e.target.value) })}
                    className="input-field"
                    min="320"
                    max="1280"
                    step="32"
                  />
                </div>
                <div>
                  <label htmlFor="device" className="label-field">دستگاه</label>
                  <select
                    id="device"
                    value={detectionForm.device}
                    onChange={(e) => setDetectionForm({ ...detectionForm, device: e.target.value })}
                    className="input-field"
                  >
                    <option value="auto">خودکار</option>
                    <option value="cpu">CPU</option>
                    <option value="0">GPU 0</option>
                    <option value="1">GPU 1</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="batch_size" className="label-field">حجم دسته</label>
                  <input
                    id="batch_size"
                    type="number"
                    value={detectionForm.batch_size}
                    onChange={(e) => setDetectionForm({ ...detectionForm, batch_size: parseInt(e.target.value) })}
                    className="input-field"
                    min="1"
                    max="16"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="batch_window_ms" className="label-field">پنجره دسته‌بندی (میلی‌ثانیه)</label>
                <input
                  id="batch_window_ms"
                  type="number"
                  value={detectionForm.batch_window_ms}
                  onChange={(e) => setDetectionForm({ ...detectionForm, batch_window_ms: parseInt(e.target.value) })}
                  className="input-field"
                  min="10"
                  max="200"
                />
              </div>

              <div className="flex justify-end pt-5 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => handleSave('detection')}
                  disabled={saving}
                  className="btn-primary"
                >
                  {saving ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <CheckIcon className="w-5 h-5" />
                      ذخیره تنظیمات تشخیص
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Counting Tab */}
          {activeTab === 'counting' && (
            <form className="space-y-5 max-w-2xl">
              <div>
                <label htmlFor="track_point" className="label-field">نقطه ردیابی</label>
                <select
                  id="track_point"
                  value={countingForm.track_point}
                  onChange={(e) => setCountingForm({ ...countingForm, track_point: e.target.value })}
                  className="input-field"
                >
                  <option value="bottom">پایین (پاها)</option>
                  <option value="center">مرکز</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">نقطه بدنه برای تشخیص عبور از خط/منطقه</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="counting_cooldown_s" className="label-field">کول‌داون شمارش (ثانیه)</label>
                  <input
                    id="counting_cooldown_s"
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="10"
                    value={countingForm.counting_cooldown_s}
                    onChange={(e) => setCountingForm({ ...countingForm, counting_cooldown_s: parseFloat(e.target.value) })}
                    className="input-field"
                  />
                </div>
                <div>
                  <label htmlFor="counting_min_displacement" className="label-field">حداقل جابجایی</label>
                  <input
                    id="counting_min_displacement"
                    type="number"
                    step="0.001"
                    min="0.001"
                    max="0.1"
                    value={countingForm.counting_min_displacement}
                    onChange={(e) => setCountingForm({ ...countingForm, counting_min_displacement: parseFloat(e.target.value) })}
                    className="input-field"
                  />
                  <p className="text-xs text-gray-500 mt-1">به نسبت عرض تصویر (0.015 = ۱.۵٪)</p>
                </div>
              </div>

              <div className="flex justify-end pt-5 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => handleSave('counting')}
                  disabled={saving}
                  className="btn-primary"
                >
                  {saving ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <CheckIcon className="w-5 h-5" />
                      ذخیره تنظیمات شمارش
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* API Tab */}
          {activeTab === 'api' && (
            <form className="space-y-5 max-w-2xl">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={apiForm.api_enabled}
                    onChange={(e) => setApiForm({ ...apiForm, api_enabled: e.target.checked })}
                    className="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">فعال‌سازی API سرور</span>
                </label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="api_host" className="label-field">هاست</label>
                  <input
                    id="api_host"
                    type="text"
                    value={apiForm.api_host}
                    onChange={(e) => setApiForm({ ...apiForm, api_host: e.target.value })}
                    className="input-field"
                    placeholder="127.0.0.1"
                  />
                </div>
                <div>
                  <label htmlFor="api_port" className="label-field">پورت</label>
                  <input
                    id="api_port"
                    type="number"
                    value={apiForm.api_port}
                    onChange={(e) => setApiForm({ ...apiForm, api_port: parseInt(e.target.value) })}
                    className="input-field"
                    min="1"
                    max="65535"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="cors_origins" className="label-field">مجازهای CORS</label>
                <input
                  id="cors_origins"
                  type="text"
                  value={apiForm.cors_origins}
                  onChange={(e) => setApiForm({ ...apiForm, cors_origins: e.target.value })}
                  className="input-field"
                  placeholder="http://localhost:3000, https://example.com"
                />
                <p className="text-xs text-gray-500 mt-1">آدرس‌ها را با کاما جدا کنید. * برای همه</p>
              </div>

              <div>
                <label htmlFor="rate_limit" className="label-field">محدودیت نرخ ورود (در دقیقه)</label>
                <input
                  id="rate_limit"
                  type="number"
                  value={apiForm.rate_limit_login_per_minute}
                  onChange={(e) => setApiForm({ ...apiForm, rate_limit_login_per_minute: parseInt(e.target.value) })}
                  className="input-field"
                  min="1"
                  max="100"
                />
              </div>

              <div className="flex justify-end pt-5 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => handleSave('api')}
                  disabled={saving}
                  className="btn-primary"
                >
                  {saving ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <CheckIcon className="w-5 h-5" />
                      ذخیره تنظیمات API
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="max-w-2xl space-y-8">
              <div className="p-5 bg-blue-50 rounded-xl border border-blue-100">
                <div className="flex items-start gap-3">
                  <ShieldCheckIcon className="w-6 h-6 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-gray-900">تغییر رمز عبور</h3>
                    <p className="text-sm text-gray-600 mt-1">برای امنیت حساب کاربری خود، رمز عبور را به صورت منظم تغییر دهید</p>
                  </div>
                </div>
              </div>

              <form onSubmit={handleChangePassword} className="space-y-5">
                <div>
                  <label htmlFor="current_password" className="label-field">رمز عبور فعلی</label>
                  <input
                    id="current_password"
                    type="password"
                    value={passwordForm.current_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                    className="input-field"
                    required
                    autoComplete="current-password"
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
                    required
                    minLength={6}
                    autoComplete="new-password"
                  />
                </div>

                <div>
                  <label htmlFor="confirm_password" className="label-field">تایید رمز عبور جدید</label>
                  <input
                    id="confirm_password"
                    type="password"
                    value={passwordForm.confirm_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                    className="input-field"
                    required
                    autoComplete="new-password"
                  />
                </div>

                <div className="flex justify-end pt-5 border-t border-gray-100">
                  <button
                    type="submit"
                    disabled={saving}
                    className="btn-primary"
                  >
                    {saving ? (
                      <span className="flex items-center gap-2">
                        <svg className="spinner" />
                        در حال تغییر...
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <KeyIcon className="w-5 h-5" />
                        تغییر رمز عبور
                      </span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}