import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { type Camera, type Line, type LineCreate, type Area, type AreaCreate } from '../api/types';
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  Squares2X2Icon,
  MinusIcon,
  XMarkIcon,
  CheckIcon,
  RectangleStackIcon,
  MinusCircleIcon,
} from '@heroicons/react/24/outline';

type ZoneKind = 'line' | 'area';

interface FormState {
  kind: ZoneKind;
  name: string;
  color: string;
  enabled: boolean;
  // line
  x1: string;
  y1: string;
  x2: string;
  y2: string;
  direction: 'A_TO_B' | 'B_TO_A' | 'BOTH';
  // area
  points: number[][];
}

const emptyForm = (): FormState => ({
  kind: 'line',
  name: '',
  color: '#22c55e',
  enabled: true,
  x1: '0.2',
  y1: '0.5',
  x2: '0.8',
  y2: '0.5',
  direction: 'BOTH',
  points: [
    [0.2, 0.2],
    [0.8, 0.2],
    [0.8, 0.8],
    [0.2, 0.8],
  ],
});

export function ZonesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(
    searchParams.get('camera') ? parseInt(searchParams.get('camera')!) : null
  );
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<{ kind: ZoneKind; id: number } | null>(null);
  const [formData, setFormData] = useState<FormState>(emptyForm());
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
      const [l, a] = await Promise.all([
        api.getLines(selectedCameraId),
        api.getAreas(selectedCameraId),
      ]);
      setLines(l);
      setAreas(a);
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
  }, [fetchZones]);

  const handleCameraChange = (cameraId: number) => {
    setSelectedCameraId(cameraId);
    setSearchParams({ camera: cameraId.toString() });
  };

  const openCreateModal = (kind: ZoneKind) => {
    setEditing(null);
    setFormData(emptyForm());
    setFormData((f) => ({ ...f, kind, color: kind === 'line' ? '#22c55e' : '#3b82f6' }));
    setFormErrors({});
    setShowModal(true);
  };

  const openEditModal = (kind: ZoneKind, item: Line | Area) => {
    setEditing({ kind, id: item.id });
    if (kind === 'line') {
      const l = item as Line;
      setFormData({
        kind,
        name: l.name,
        color: l.color,
        enabled: l.enabled,
        x1: String(l.x1),
        y1: String(l.y1),
        x2: String(l.x2),
        y2: String(l.y2),
        direction: l.direction,
        points: [],
      });
    } else {
      const a = item as Area;
      setFormData({
        kind,
        name: a.name,
        color: a.color,
        enabled: a.enabled,
        x1: '',
        y1: '',
        x2: '',
        y2: '',
        direction: 'BOTH',
        points: a.points.map((p) => [p[0], p[1]]),
      });
    }
    setFormErrors({});
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditing(null);
    setFormErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!formData.name.trim()) errors.name = 'نام الزامی است';
    if (formData.kind === 'line') {
      const vals = [formData.x1, formData.y1, formData.x2, formData.y2].map(Number);
      if (vals.some((v) => Number.isNaN(v) || v < 0 || v > 1)) {
        errors.coords = 'مختصات باید عددی بین ۰ و ۱ باشند';
      }
    } else if (formData.points.length < 3) {
      errors.coords = 'منطقه باید حداقل ۳ نقطه داشته باشد';
    } else if (formData.points.some((p) => p.some((v) => Number.isNaN(v) || v < 0 || v > 1))) {
      errors.coords = 'مختصات باید عددی بین ۰ و ۱ باشند';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm() || !selectedCameraId) return;

    setSubmitting(true);
    try {
      if (formData.kind === 'line') {
        const payload: LineCreate = {
          name: formData.name,
          x1: Number(formData.x1),
          y1: Number(formData.y1),
          x2: Number(formData.x2),
          y2: Number(formData.y2),
          direction: formData.direction,
          color: formData.color,
          enabled: formData.enabled,
        };
        if (editing?.kind === 'line') {
          await api.updateLine(selectedCameraId, editing.id, payload);
        } else {
          await api.createLine(selectedCameraId, payload);
        }
      } else {
        const payload: AreaCreate = {
          name: formData.name,
          points: formData.points,
          color: formData.color,
          enabled: formData.enabled,
        };
        if (editing?.kind === 'area') {
          await api.updateArea(selectedCameraId, editing.id, payload);
        } else {
          await api.createArea(selectedCameraId, payload);
        }
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

  const handleDelete = async (kind: ZoneKind, id: number) => {
    if (!selectedCameraId) return;
    if (!window.confirm('آیا از حذف مطمئن هستید؟')) return;
    try {
      if (kind === 'line') {
        await api.deleteLine(selectedCameraId, id);
        setLines((prev) => prev.filter((l) => l.id !== id));
      } else {
        await api.deleteArea(selectedCameraId, id);
        setAreas((prev) => prev.filter((a) => a.id !== id));
      }
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const handleOpenEditor = async (cameraId: number) => {
    // Open the current camera snapshot in a new tab as a visual reference.
    try {
      const url = await api.getCameraSnapshot(cameraId);
      window.open(url, '_blank');
    } catch (err: any) {
      console.error('Failed to open snapshot:', err);
    }
  };

  const zoneColors = [
    '#22c55e', '#3b82f6', '#16a34a', '#dc2626', '#f59e0b',
    '#9333ea', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  ];

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId);
  const allZones = [
    ...lines.map((l) => ({
      id: l.id,
      kind: 'line' as ZoneKind,
      name: l.name,
      color: l.color,
      enabled: l.enabled,
      detail: `(${l.x1.toFixed(3)},${l.y1.toFixed(3)}) → (${l.x2.toFixed(3)},${l.y2.toFixed(3)})`,
      directionLabel: l.direction === 'A_TO_B' ? 'A→B' : l.direction === 'B_TO_A' ? 'B→A' : 'هر دو جهت',
    })),
    ...areas.map((a) => ({
      id: a.id,
      kind: 'area' as ZoneKind,
      name: a.name,
      color: a.color,
      enabled: a.enabled,
      detail: `${a.points.length} نقطه`,
      directionLabel: '—',
    })),
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">منطقه‌ها و خطوط شمارش</h1>
          <p className="text-gray-500 mt-1">تعریف خطوط و مناطق برای شمارش ورودی و خروجی</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => openCreateModal('line')}
            disabled={!selectedCameraId}
            className="btn-primary"
          >
            <PlusIcon className="w-5 h-5 ml-2" />
            خط شمارش
          </button>
          <button
            onClick={() => openCreateModal('area')}
            disabled={!selectedCameraId}
            className="btn-primary"
          >
            <RectangleStackIcon className="w-5 h-5 ml-2" />
            منطقه شمارش
          </button>
          {selectedCameraId && (
            <button onClick={() => handleOpenEditor(selectedCameraId)} className="btn-secondary">
              <Squares2X2Icon className="w-5 h-5 ml-2" />
              نمای لحظه‌ای دوربین
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
              <option value="">دوربین انتخاب کنید</option>
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
              <h3 className="empty-state-title">دوربین انتخاب نشده</h3>
              <p className="empty-state-description">برای مدیریت منطقه‌ها، یک دوربین را از منوی بالا انتخاب کنید</p>
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center h-64">
              <svg className="spinner-lg" />
            </div>
          ) : allZones.length === 0 ? (
            <div className="empty-state h-64">
              <Squares2X2Icon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">هیچ منطقه‌ای تعریف نشده</h3>
              <p className="empty-state-description">برای شروع، اولین خط یا منطقه شمارش را اضافه کنید</p>
              <button onClick={() => openCreateModal('line')} className="btn-primary mt-4">
                <PlusIcon className="w-5 h-5 ml-2" />
                افزودن خط شمارش
              </button>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>نوع</th>
                    <th>نام</th>
                    <th>جهت</th>
                    <th>رنگ</th>
                    <th>مختصات</th>
                    <th>وضعیت</th>
                    <th className="text-left">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {allZones.map((zone) => (
                    <tr key={`${zone.kind}-${zone.id}`} className="hover:bg-gray-50">
                      <td>
                        <span className={`badge ${zone.kind === 'line' ? 'badge-info' : 'badge-success'}`}>
                          {zone.kind === 'line' ? 'خط' : 'منطقه'}
                        </span>
                      </td>
                      <td className="font-medium text-gray-900">{zone.name}</td>
                      <td>
                        <span className="text-sm text-gray-600">{zone.directionLabel}</span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded border border-gray-300" style={{ backgroundColor: zone.color }} />
                          <span className="text-xs text-gray-500 font-mono">{zone.color}</span>
                        </div>
                      </td>
                      <td>
                        <span className="text-xs text-gray-500 font-mono max-w-xs truncate block">{zone.detail}</span>
                      </td>
                      <td>
                        <span className={zone.enabled ? 'badge badge-success' : 'badge badge-gray'}>
                          {zone.enabled ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2 text-left">
                          <button
                            onClick={() => openEditModal(zone.kind, zone.kind === 'line' ? lines.find((l) => l.id === zone.id)! : areas.find((a) => a.id === zone.id)!)}
                            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                            aria-label="ویرایش"
                          >
                            <PencilIcon className="w-5 h-5" />
                          </button>
                          <button
                            onClick={() => handleDelete(zone.kind, zone.id)}
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
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal} role="dialog" aria-modal="true" aria-labelledby="zone-modal-title">
          <div className="modal-content max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="card-header flex items-center justify-between">
              <h2 id="zone-modal-title" className="text-lg font-semibold text-gray-900">
                {editing ? 'ویرایش' : 'افزودن'}{formData.kind === 'line' ? ' خط شمارش' : ' منطقه شمارش'}
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
                <label htmlFor="zone-name" className="label-field">نام <span className="text-red-500">*</span></label>
                <input
                  id="zone-name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`input-field ${formErrors.name ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder={formData.kind === 'line' ? 'مثال: خط ورودی اصلی' : 'مثال: منطقه پیشخوان'}
                />
                {formErrors.name && <p className="text-red-500 text-sm mt-1">{formErrors.name}</p>}
              </div>

              {formData.kind === 'line' ? (
                <div>
                  <label className="label-field">جهت شمارش</label>
                  <select
                    value={formData.direction}
                    onChange={(e) => setFormData({ ...formData, direction: e.target.value as FormState['direction'] })}
                    className="input-field"
                  >
                    <option value="BOTH">هر دو جهت</option>
                    <option value="A_TO_B">فقط A به B</option>
                    <option value="B_TO_A">فقط B به A</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    A نقطه شروع و B نقطه پایان خط است. مسیر عبور افراد با راست به چپ یا چپ به راست خط تعیین می‌شود.
                  </p>
                </div>
              ) : null}

              <div>
                <label className="label-field">رنگ نمایش</label>
                <div className="flex flex-wrap items-center gap-3">
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

              {formData.kind === 'line' ? (
                <div>
                  <label className="label-field">مختصات خط (نسبی ۰-۱)</label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <PointInput label="X1 (A)" value={formData.x1} onChange={(v) => setFormData({ ...formData, x1: v })} />
                    <PointInput label="Y1 (A)" value={formData.y1} onChange={(v) => setFormData({ ...formData, y1: v })} />
                    <PointInput label="X2 (B)" value={formData.x2} onChange={(v) => setFormData({ ...formData, x2: v })} />
                    <PointInput label="Y2 (B)" value={formData.y2} onChange={(v) => setFormData({ ...formData, y2: v })} />
                  </div>
                  {formErrors.coords && <p className="text-red-500 text-sm mt-1">{formErrors.coords}</p>}
                </div>
              ) : (
                <div>
                  <label className="label-field">رئوس منطقه (نسبی ۰-۱)</label>
                  <PolygonInput
                    points={formData.points}
                    onChange={(points) => setFormData({ ...formData, points })}
                    error={formErrors.coords}
                  />
                </div>
              )}

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
                      {editing ? 'به‌روزرسانی' : 'افزودن'}
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

function PointInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-gray-500">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field"
        min="0"
        max="1"
        step="0.001"
      />
    </div>
  );
}

function PolygonInput({
  points,
  onChange,
  error,
}: {
  points: number[][];
  onChange: (points: number[][]) => void;
  error?: string;
}) {
  const updatePoint = (index: number, axis: 0 | 1, value: number) => {
    const next = points.map((p, i) => (i === index ? (axis === 0 ? [value, p[1]] : [p[0], value]) : p));
    onChange(next);
  };

  const removePoint = (index: number) => {
    if (points.length <= 3) return;
    onChange(points.filter((_, i) => i !== index));
  };

  const addPoint = () => onChange([...points, [0.5, 0.5]]);

  return (
    <div className="space-y-2">
      {points.map((point, index) => (
        <div key={index} className="flex items-center gap-2">
          <span className="w-8 text-center text-sm text-gray-500">{index + 1}</span>
          <input
            type="number"
            value={point[0]}
            onChange={(e) => updatePoint(index, 0, parseFloat(e.target.value) || 0)}
            className="input-field w-24"
            placeholder="X"
            min="0"
            max="1"
            step="0.001"
          />
          <input
            type="number"
            value={point[1]}
            onChange={(e) => updatePoint(index, 1, parseFloat(e.target.value) || 0)}
            className="input-field w-24"
            placeholder="Y"
            min="0"
            max="1"
            step="0.001"
          />
          <span className="text-xs text-gray-400">(نسبی ۰-۱)</span>
          {points.length > 3 && (
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
      <div className="flex gap-2">
        <button type="button" onClick={addPoint} className="btn-outline btn-sm">
          <PlusIcon className="w-4 h-4 ml-1" />
          افزودن نقطه
        </button>
        <span className="text-xs text-gray-400 flex items-center gap-1">
          <MinusCircleIcon className="w-4 h-4" />
          حداقل ۳ نقطه
        </span>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}
    </div>
  );
}
