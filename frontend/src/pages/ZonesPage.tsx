import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { type Camera, type Zone, type ZoneCreate } from '../api/types';
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  Squares2X2Icon,
  MinusIcon,
  XMarkIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

export function ZonesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(
    searchParams.get('camera') ? parseInt(searchParams.get('camera')!) : null
  );
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [formData, setFormData] = useState<ZoneCreate>({
    name: '',
    zone_type: 'line',
    coordinates: [],
    direction: 'both',
    color: '#2563eb',
    enabled: true,
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const fetchCameras = useCallback(async () => {
    try {
      const res = await api.getCameras({ size: 100 });
      setCameras(res.items);
      if (!selectedCameraId && res.items.length > 0) {
        setSelectedCameraId(res.items[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch cameras:', err);
    }
  }, [selectedCameraId]);

  const fetchZones = useCallback(async () => {
    if (!selectedCameraId) return;
    setLoading(true);
    try {
      const data = await api.getZones(selectedCameraId);
      setZones(data);
    } catch (err) {
      console.error('Failed to fetch zones:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedCameraId]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  useEffect(() => {
    fetchZones();
  }, [fetchZones, selectedCameraId]);

  const handleCameraChange = (cameraId: number) => {
    setSelectedCameraId(cameraId);
    setSearchParams({ camera: cameraId.toString() });
  };

  const openCreateModal = () => {
    setEditingZone(null);
    setFormData({
      name: '',
      zone_type: 'line',
      coordinates: [],
      direction: 'both',
      color: '#2563eb',
      enabled: true,
    });
    setFormErrors({});
    setShowModal(true);
  };

  const openEditModal = (zone: Zone) => {
    setEditingZone(zone);
    setFormData({
      name: zone.name,
      zone_type: zone.zone_type,
      coordinates: zone.coordinates,
      direction: zone.direction,
      color: zone.color,
      enabled: zone.enabled,
    });
    setFormErrors({});
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingZone(null);
    setFormErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!formData.name.trim()) errors.name = 'نام منطقه الزامی است';
    if (formData.zone_type === 'line' && formData.coordinates.length !== 2) {
      errors.coordinates = 'خط شمارش باید دقیقاً ۲ نقطه داشته باشد';
    }
    if (formData.zone_type === 'area' && formData.coordinates.length < 3) {
      errors.coordinates = 'منطقه شمارش باید حداقل ۳ نقطه داشته باشد';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm() || !selectedCameraId) return;

    setSubmitting(true);
    try {
      if (editingZone) {
        await api.updateZone(selectedCameraId, editingZone.id, formData);
      } else {
        await api.createZone(selectedCameraId, formData);
      }
      closeModal();
      fetchZones();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setFormErrors({ submit: err.response.data.detail });
      } else {
        setFormErrors({ submit: 'خطا در ذخیره منطقه' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (zone: Zone) => {
    if (!selectedCameraId) return;
    if (!window.confirm(`آیا از حذف منطقه "${zone.name}" مطمئن هستید؟`)) return;
    try {
      await api.deleteZone(selectedCameraId, zone.id);
      setZones((prev) => prev.filter((z) => z.id !== zone.id));
    } catch (err) {
      console.error('Failed to delete zone:', err);
    }
  };

  const handleOpenEditor = (cameraId: number) => {
    navigate(`/zones/editor/${cameraId}`);
  };

  const zoneColors = [
    '#2563eb', '#16a34a', '#dc2626', '#f59e0b', '#9333ea',
    '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  ];

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">منطقه‌ها و خطوط شمارش</h1>
          <p className="text-gray-500 mt-1">تعریف خطوط و مناطق برای شمارش ورودی و خروجی</p>
        </div>
        <div className="flex gap-3">
          <button onClick={openCreateModal} disabled={!selectedCameraId} className="btn-primary">
            <PlusIcon className="w-5 h-5 ml-2" />
            افزودن منطقه
          </button>
          {selectedCameraId && (
            <button onClick={() => handleOpenEditor(selectedCameraId)} className="btn-secondary">
              <Squares2X2Icon className="w-5 h-5 ml-2" />
              ویرایشگر بصری
            </button>
          )}
        </div>
      </div>

      {/* Camera Selector */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <label className="label-field mb-0 whitespace-nowrap">دوربین:</label>
            <select
              value={selectedCameraId || ''}
              onChange={(e) => handleCameraChange(parseInt(e.target.value))}
              className="input-field w-full sm:w-64"
            >
              <option value="">دوربیni انتخاب کنید</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name} {camera.location && `(${camera.location})`}
                </option>
              ))}
            </select>
            {selectedCamera && (
              <div className="flex items-center gap-4 text-sm text-gray-500">
                <span className={`badge ${selectedCamera.enabled ? 'badge-success' : 'badge-gray'}`}>
                  {selectedCamera.enabled ? 'فعال' : 'غیرفعال'}
                </span>
                <span className={`live-indicator ${selectedCamera.status === 'online' ? 'online' : 'offline'}`}>
                  {selectedCamera.status === 'online' ? 'آنلاین' : 'آفلاین'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Zones List */}
      <div className="card">
        <div className="card-body p-0">
          {!selectedCameraId ? (
            <div className="empty-state h-64">
              <Squares2X2Icon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">دوربیni انتخاب نشده</h3>
              <p className="empty-state-description">برای مدیریت منطقه‌ها، یک دوربین را از منوی بالا انتخاب کنید</p>
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center h-64">
              <svg className="spinner-lg" />
            </div>
          ) : zones.length === 0 ? (
            <div className="empty-state h-64">
              <Squares2X2Icon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">هیچ منطقه‌ای تعریف نشده</h3>
              <p className="empty-state-description">برای شروع، اولین خط یا منطقه شمارش را اضافه کنید</p>
              <button onClick={openCreateModal} className="btn-primary mt-4">
                <PlusIcon className="w-5 h-5 ml-2" />
                افزودن منطقه
              </button>
            </div>
          ) : (
            <>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>نوع</th>
                      <th>نام</th>
                      <th>جهت شمارش</th>
                      <th>رنگ</th>
                      <th>مختصات</th>
                      <th>وضعیت</th>
                      <th className="text-left">عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {zones.map((zone) => (
                      <tr key={zone.id} className="hover:bg-gray-50">
                        <td>
                          <span className={`badge ${zone.zone_type === 'line' ? 'badge-info' : 'badge-success'}`}>
                            {zone.zone_type === 'line' ? 'خط' : 'منطقه'}
                          </span>
                        </td>
                        <td className="font-medium text-gray-900">{zone.name}</td>
                        <td>
                          <span className={`badge ${zone.direction === 'in' ? 'badge-info' : zone.direction === 'out' ? 'badge-warning' : 'badge-gray'}`}>
                            {zone.direction === 'in' ? 'ورود' : zone.direction === 'out' ? 'خروج' : 'هر دو'}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center gap-2">
                            <span
                              className="w-6 h-6 rounded border border-gray-300"
                              style={{ backgroundColor: zone.color }}
                            />
                            <span className="text-xs text-gray-500 font-mono">{zone.color}</span>
                          </div>
                        </td>
                        <td>
                          <span className="text-xs text-gray-500 font-mono max-w-xs truncate block">
                            {zone.coordinates.map((c) => `(${c[0]},${c[1]})`).join(' → ')}
                          </span>
                        </td>
                        <td>
                          <span className={zone.enabled ? 'badge badge-success' : 'badge badge-gray'}>
                            {zone.enabled ? 'فعال' : 'غیرفعال'}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center gap-2 text-left">
                            <button
                              onClick={() => openEditModal(zone)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                              aria-label="ویرایش"
                            >
                              <PencilIcon className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => handleDelete(zone)}
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
            </>
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal} role="dialog" aria-modal="true" aria-labelledby="zone-modal-title">
          <div className="modal-content max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="card-header flex items-center justify-between">
              <h2 id="zone-modal-title" className="text-lg font-semibold text-gray-900">
                {editingZone ? 'ویرایش منطقه' : 'افزودن منطقه جدید'}
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
                <label htmlFor="zone-name" className="label-field">نام منطقه <span className="text-red-500">*</span></label>
                <input
                  id="zone-name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`input-field ${formErrors.name ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder="مثال: خط ورودی اصلی"
                />
                {formErrors.name && <p className="text-red-500 text-sm mt-1">{formErrors.name}</p>}
              </div>

              <div>
                <label className="label-field">نوع منطقه <span className="text-red-500">*</span></label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="zone_type"
                      value="line"
                      checked={formData.zone_type === 'line'}
                      onChange={() => setFormData({ ...formData, zone_type: 'line' })}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">خط شمارش</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="zone_type"
                      value="area"
                      checked={formData.zone_type === 'area'}
                      onChange={() => setFormData({ ...formData, zone_type: 'area' })}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">منطقه شمارش</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="label-field">جهت شمارش</label>
                <select
                  value={formData.direction}
                  onChange={(e) => setFormData({ ...formData, direction: e.target.value as any })}
                  className="input-field"
                >
                  <option value="both">هر دو جهت</option>
                  <option value="in">فقط ورود</option>
                  <option value="out">فقط خروج</option>
                </select>
              </div>

              <div>
                <label className="label-field">رنگ نمایش</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="w-10 h-10 rounded-lg border border-gray-300 cursor-pointer"
                  />
                  <div className="flex flex-wrap gap-2">
                    {zoneColors.map((color) => (
                      <button
                        key={color}
                        type="button"
                        onClick={() => setFormData({ ...formData, color })}
                        className="w-8 h-8 rounded-lg border-2 transition-transform hover:scale-110"
                        style={{ backgroundColor: color, borderColor: formData.color === color ? '#1e293b' : 'transparent' }}
                        aria-label={color}
                        aria-pressed={formData.color === color}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <label className="label-field">مختصات</label>
                <div className="space-y-2">
                  <p className="text-sm text-gray-500">
                    {formData.zone_type === 'line'
                      ? 'خط شمارش نیاز به دقیقاً ۲ نقطه دارد (نقطه شروع و پایان)'
                      : 'منطقه شمارش نیاز به حداقل ۳ نقطه دارد (رأس‌های چندضلعی)'}
                  </p>
                  <CoordinatesInput
                    coordinates={formData.coordinates}
                    onChange={(coords) => setFormData({ ...formData, coordinates: coords })}
                    zoneType={formData.zone_type}
                    error={formErrors.coordinates}
                  />
                </div>
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">فعال</span>
                </label>
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
                      {editingZone ? 'به‌روزرسانی' : 'افزودن'}
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

// Coordinates Input Component
function CoordinatesInput({
  coordinates,
  onChange,
  zoneType,
  error,
}: {
  coordinates: number[][];
  onChange: (coords: number[][]) => void;
  zoneType: 'line' | 'area';
  error?: string;
}) {
  const [localCoords, setLocalCoords] = useState(coordinates);

  useEffect(() => {
    setLocalCoords(coordinates);
  }, [coordinates]);

  useEffect(() => {
    onChange(localCoords);
  }, [localCoords, onChange]);

  const addPoint = () => {
    if (zoneType === 'line' && localCoords.length >= 2) return;
    setLocalCoords([...localCoords, [0, 0]]);
  };

  const removePoint = (index: number) => {
    const newCoords = localCoords.filter((_, i) => i !== index);
    setLocalCoords(newCoords);
  };

  const updatePoint = (index: number, x: number, y: number) => {
    const newCoords = [...localCoords];
    newCoords[index] = [x, y];
    setLocalCoords(newCoords);
  };

  return (
    <div className="space-y-2">
      {localCoords.map((point, index) => (
        <div key={index} className="flex items-center gap-2">
          <span className="w-8 text-center text-sm text-gray-500">{index + 1}</span>
          <input
            type="number"
            value={point[0]}
            onChange={(e) => updatePoint(index, parseFloat(e.target.value) || 0, point[1])}
            className="input-field w-24"
            placeholder="X"
            min="0"
            max="1"
            step="0.001"
          />
          <input
            type="number"
            value={point[1]}
            onChange={(e) => updatePoint(index, point[0], parseFloat(e.target.value) || 0)}
            className="input-field w-24"
            placeholder="Y"
            min="0"
            max="1"
            step="0.001"
          />
          <span className="text-xs text-gray-400">(نسبی ۰-۱)</span>
          {localCoords.length > (zoneType === 'line' ? 2 : 3) && (
            <button
              type="button"
              onClick={() => removePoint(index)}
              className="p-1 text-red-500 hover:text-red-700 rounded"
              aria-label={`حذف نقطه ${index + 1}`}
            >
              <MinusIcon className="w-5 h-5" />
            </button>
          )}
        </div>
      ))}
      {(zoneType === 'line' && localCoords.length < 2) || (zoneType === 'area' && localCoords.length < 10) ? (
        <button type="button" onClick={addPoint} className="btn-outline btn-sm">
          <PlusIcon className="w-4 h-4 ml-1" />
          افزودن نقطه
        </button>
      ) : null}
      {error && <p className="text-red-500 text-sm">{error}</p>}
    </div>
  );
}