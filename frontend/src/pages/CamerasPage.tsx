import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { type Camera, type CameraCreate } from '../api/types';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  TrashIcon,
  EyeIcon,
  Cog6ToothIcon,
  PlayIcon,
  PauseIcon,
  XMarkIcon,
  CheckIcon,
  VideoCameraIcon,
} from '@heroicons/react/24/outline';

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

export function CamerasPage() {
  const navigate = useNavigate();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [showModal, setShowModal] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [formData, setFormData] = useState<CameraForm>(emptyForm());
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getCameras({ page, size: 20, search: search || undefined });
      // Client-side pagination over the array the backend returns.
      const start = (page - 1) * 20;
      setCameras(res.items.slice(start, start + 20));
      setTotalPages(res.pages);
      setTotalItems(res.total);
    } catch (err) {
      console.error('Failed to fetch cameras:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const openCreateModal = () => {
    setEditingCamera(null);
    setFormData(emptyForm());
    setFormErrors({});
    setShowModal(true);
  };

  const openEditModal = (camera: Camera) => {
    setEditingCamera(camera);
    setFormData({
      name: camera.name,
      location: camera.location || '',
      mode: camera.source_type === 'file' ? 'file' : 'manual',
      host: camera.host || '',
      port: camera.port || 554,
      username: camera.username || '',
      password: '',
      rtsp_path: camera.rtsp_path || '',
      url: '',
      file_path: camera.file_path || '',
      fps_limit: camera.fps_limit || 10,
      detection_enabled: camera.detection_enabled,
      enabled: camera.enabled,
    });
    setFormErrors({});
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingCamera(null);
    setFormErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!formData.name.trim()) errors.name = 'نام دوربین الزامی است';
    if (formData.mode === 'url' && !(formData.url || '').trim()) {
      errors.url = 'آدرس RTSP الزامی است';
    }
    if (formData.mode === 'manual' && !(formData.host || '').trim()) {
      errors.host = 'آدرس IP الزامی است';
    }
    if (formData.mode === 'file' && !(formData.file_path || '').trim()) {
      errors.file_path = 'مسیر فایل الزامی است';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      const submitData: CameraCreate = {
        name: formData.name,
        location: formData.location,
        mode: formData.mode,
        fps_limit: formData.fps_limit,
        detection_enabled: formData.detection_enabled,
        enabled: formData.enabled,
      };
      if (formData.mode === 'url') {
        submitData.url = formData.url;
      } else if (formData.mode === 'file') {
        submitData.file_path = formData.file_path;
      } else {
        submitData.host = formData.host;
        submitData.port = formData.port;
        submitData.username = formData.username || undefined;
        submitData.rtsp_path = formData.rtsp_path || '';
      }
      // Only send a password when the user typed one.
      if (formData.password) submitData.password = formData.password;

      if (editingCamera) {
        await api.updateCamera(editingCamera.id, submitData);
      } else {
        await api.createCamera(submitData);
      }
      closeModal();
      fetchCameras();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setFormErrors({ submit: err.response.data.detail });
      } else {
        setFormErrors({ submit: 'خطا در ذخیره دوربین' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (camera: Camera) => {
    try {
      await api.toggleCamera(camera.id, !camera.enabled);
      setCameras((prev) =>
        prev.map((c) => (c.id === camera.id ? { ...c, enabled: !camera.enabled } : c))
      );
    } catch (err) {
      console.error('Failed to toggle camera:', err);
    }
  };

  const handleDelete = async (camera: Camera) => {
    if (!window.confirm(`آیا از حذف دوربین "${camera.name}" مطمئن هستید؟`)) return;
    try {
      await api.deleteCamera(camera.id);
      setCameras((prev) => prev.filter((c) => c.id !== camera.id));
      setTotalItems((prev) => prev - 1);
    } catch (err) {
      console.error('Failed to delete camera:', err);
    }
  };

  const handleView = (camera: Camera) => {
    navigate(`/cameras/${camera.id}`);
  };

  const handleZones = (camera: Camera) => {
    navigate(`/zones?camera=${camera.id}`);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">مدیریت دوربین‌ها</h1>
          <p className="text-gray-500 mt-1">افزودن، ویرایش و نظارت بر دوربین‌های شمارش</p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="w-5 h-5 ml-2" />
          افزودن دوربین
        </button>
      </div>

      {/* Search and Filter */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="search"
                placeholder="جستجو در نام، مکان، آدرس..."
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                className="input-field pr-10"
              />
            </div>
            <div className="flex gap-2">
              <select className="input-field w-auto" defaultValue="all">
                <option value="all">همه وضعیت‌ها</option>
                <option value="online">آنلاین</option>
                <option value="offline">آفلاین</option>
                <option value="enabled">فعال</option>
                <option value="disabled">غیرفعال</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Cameras Table */}
      <div className="card">
        <div className="card-body p-0">
          {loading && cameras.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <svg className="spinner-lg" />
            </div>
          ) : cameras.length === 0 ? (
            <div className="empty-state h-64">
              <VideoCameraIcon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">هیچ دوربینی یافت نشد</h3>
              <p className="empty-state-description">
                {search ? 'تلاش کنید با کلمات کلیدی دیگر جستجو کنید' : 'برای شروع، اولین دوربین خود را اضافه کنید'}
              </p>
              {!search && (
                <button onClick={openCreateModal} className="btn-primary mt-4">
                  <PlusIcon className="w-5 h-5 ml-2" />
                  افزودن دوربین
                </button>
              )}
            </div>
          ) : (
            <>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>دوربین</th>
                      <th>منبع</th>
                      <th>موقعیت</th>
                      <th>وضعیت</th>
                      <th>تشخیص</th>
                      <th>FPS</th>
                      <th className="text-left">عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cameras.map((camera) => (
                      <tr key={camera.id} className="hover:bg-gray-50">
                        <td>
                          <div>
                            <p className="font-medium text-gray-900">{camera.name}</p>
                            {camera.id && (
                              <p className="text-xs text-gray-400">شناسه: {camera.id}</p>
                            )}
                          </div>
                        </td>
                        <td>
                          <div className="flex items-center gap-2">
                            <span className="badge badge-info text-xs">
                              {camera.source_type === 'file' ? 'فایل' : 'RTSP'}
                            </span>
                            <span className="text-xs text-gray-500 truncate max-w-xs">
                              {camera.source_type === 'file'
                                ? camera.file_path
                                : camera.rtsp_url || `${camera.host || ''}:${camera.port || ''}`}
                            </span>
                          </div>
                        </td>
                        <td>
                          {camera.location ? (
                            <span className="text-gray-600">{camera.location}</span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td>
                          <span className={`live-indicator ${camera.enabled ? (camera.status === 'online' ? 'online' : 'offline') : 'offline'}`}>
                            {camera.enabled ? (camera.status === 'online' ? 'آنلاین' : 'آفلاین') : 'غیرفعال'}
                          </span>
                        </td>
                        <td>
                          <span className={camera.detection_enabled ? 'badge badge-success' : 'badge badge-gray'}>
                            {camera.detection_enabled ? 'فعال' : 'غیرفعال'}
                          </span>
                        </td>
                        <td>
                          <span className="text-gray-600 font-mono">{camera.live_fps?.toFixed(1) || '0.0'}</span>
                        </td>
                        <td>
                          <div className="flex items-center gap-2 text-left">
                            <button
                              onClick={() => handleView(camera)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                              aria-label="مشاهده"
                            >
                              <EyeIcon className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => handleZones(camera)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                              aria-label="منطقه‌ها"
                            >
                              <Cog6ToothIcon className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => openEditModal(camera)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                              aria-label="ویرایش"
                            >
                              <PencilIcon className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => handleToggle(camera)}
                              className={`p-2 rounded-lg transition-colors ${
                                camera.enabled
                                  ? 'text-orange-500 hover:text-orange-700 hover:bg-orange-100'
                                  : 'text-green-500 hover:text-green-700 hover:bg-green-100'
                              }`}
                              aria-label={camera.enabled ? 'غیرفعال کردن' : 'فعال کردن'}
                            >
                              {camera.enabled ? <PauseIcon className="w-5 h-5" /> : <PlayIcon className="w-5 h-5" />}
                            </button>
                            <button
                              onClick={() => handleDelete(camera)}
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

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal} role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="card-header flex items-center justify-between">
              <h2 id="modal-title" className="text-lg font-semibold text-gray-900">
                {editingCamera ? 'ویرایش دوربین' : 'افزودن دوربین جدید'}
              </h2>
              <button onClick={closeModal} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="card-body space-y-5">
              {formErrors.submit && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-center gap-2">
                  <XMarkIcon className="w-5 h-5" />
                  {formErrors.submit}
                </div>
              )}

              <div>
                <label htmlFor="name" className="label-field">نام دوربین <span className="text-red-500">*</span></label>
                <input
                  id="name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`input-field ${formErrors.name ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder="مثال: ورودی اصلی"
                />
                {formErrors.name && <p className="text-red-500 text-sm mt-1">{formErrors.name}</p>}
              </div>

              <div>
                <label htmlFor="location" className="label-field">موقعیت</label>
                <input
                  id="location"
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  className="input-field"
                  placeholder="مثال: لابی طبقه اول"
                />
              </div>

              <div>
                <label htmlFor="mode" className="label-field">نوع اتصال <span className="text-red-500">*</span></label>
                <select
                  id="mode"
                  value={formData.mode}
                  onChange={(e) => setFormData({ ...formData, mode: e.target.value as CameraForm['mode'] })}
                  className="input-field"
                >
                  <option value="url">آدرس کامل RTSP</option>
                  <option value="manual">IP + کاربر + رمز</option>
                  <option value="file">فایل ویدیویی</option>
                </select>
              </div>

              {formData.mode === 'url' && (
                <div>
                  <label htmlFor="url" className="label-field">آدرس RTSP <span className="text-red-500">*</span></label>
                  <input
                    id="url"
                    type="text"
                    value={formData.url || ''}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                    className={`input-field ${formErrors.url ? 'border-red-500 focus:ring-red-500' : ''}`}
                    placeholder="rtsp://user:pass@ip:554/stream"
                  />
                  {formErrors.url && <p className="text-red-500 text-sm mt-1">{formErrors.url}</p>}
                </div>
              )}

              {formData.mode === 'file' && (
                <div>
                  <label htmlFor="file_path" className="label-field">مسیر فایل <span className="text-red-500">*</span></label>
                  <input
                    id="file_path"
                    type="text"
                    value={formData.file_path || ''}
                    onChange={(e) => setFormData({ ...formData, file_path: e.target.value })}
                    className={`input-field ${formErrors.file_path ? 'border-red-500 focus:ring-red-500' : ''}`}
                    placeholder="C:\\videos\\sample.mp4"
                  />
                  {formErrors.file_path && <p className="text-red-500 text-sm mt-1">{formErrors.file_path}</p>}
                </div>
              )}

              {formData.mode === 'manual' && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="sm:col-span-2">
                      <label htmlFor="host" className="label-field">آدرس IP <span className="text-red-500">*</span></label>
                      <input
                        id="host"
                        type="text"
                        value={formData.host || ''}
                        onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                        className={`input-field ${formErrors.host ? 'border-red-500 focus:ring-red-500' : ''}`}
                        placeholder="192.168.1.100"
                      />
                      {formErrors.host && <p className="text-red-500 text-sm mt-1">{formErrors.host}</p>}
                    </div>
                    <div>
                      <label htmlFor="port" className="label-field">پورت</label>
                      <input
                        id="port"
                        type="number"
                        value={formData.port || 554}
                        onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) || 554 })}
                        className="input-field"
                        min="1"
                        max="65535"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="rtsp_path" className="label-field">مسیر RTSP</label>
                    <input
                      id="rtsp_path"
                      type="text"
                      value={formData.rtsp_path || ''}
                      onChange={(e) => setFormData({ ...formData, rtsp_path: e.target.value })}
                      className="input-field"
                      placeholder="/Streaming/Channels/101"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="username" className="label-field">نام کاربری</label>
                      <input
                        id="username"
                        type="text"
                        value={formData.username || ''}
                        onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                        className="input-field"
                        placeholder="اختیاری"
                      />
                    </div>
                    <div>
                      <label htmlFor="password" className="label-field">رمز عبور</label>
                      <input
                        id="password"
                        type="password"
                        value={formData.password || ''}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="input-field"
                        placeholder={editingCamera ? 'خالی بگذارید تا تغییر نکند' : 'اختیاری'}
                        autoComplete="new-password"
                      />
                    </div>
                  </div>
                </>
              )}

              <div>
                <label htmlFor="fps_limit" className="label-field">محدودیت FPS (نرخ پردازش)</label>
                <input
                  id="fps_limit"
                  type="number"
                  value={formData.fps_limit || 10}
                  onChange={(e) => setFormData({ ...formData, fps_limit: parseFloat(e.target.value) || 10 })}
                  className="input-field"
                  min="1"
                  max="60"
                  step="1"
                />
                <p className="text-xs text-gray-500 mt-1">حداکثر تعداد فریم در ثانیه برای پردازش تشخیص</p>
              </div>

              <div className="border-t border-gray-100 pt-5">
                <h3 className="font-medium text-gray-900 mb-4">تنظیمات تشخیص</h3>
                <div className="flex flex-wrap items-center gap-6">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.detection_enabled}
                      onChange={(e) => setFormData({ ...formData, detection_enabled: e.target.checked })}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">فعال‌سازی تشخیص اشیاء</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.enabled}
                      onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">دوربین فعال باشد</span>
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 border-t border-gray-100 pt-5">
                <button type="button" onClick={closeModal} className="btn-secondary">
                  انصراف
                </button>
                <button type="submit" disabled={submitting} className="btn-primary">
                  {submitting ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <CheckIcon className="w-5 h-5" />
                      {editingCamera ? 'به‌روزرسانی' : 'افزودن'}
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
