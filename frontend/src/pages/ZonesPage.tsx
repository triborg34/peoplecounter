import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { type Camera, type Line, type Area } from '../api/types';
import { ZoneCanvas } from '../components/ZoneCanvas';
import { cn, fa } from '../lib/utils';
import {
  PlusIcon,
  TrashIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  CursorArrowRaysIcon,
  MinusIcon,
  RectangleStackIcon,
} from '@heroicons/react/24/outline';

type Mode = 'select' | 'line' | 'area';

export function ZonesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(
    searchParams.get('camera') ? parseInt(searchParams.get('camera')!) : null
  );
  const [mode, setMode] = useState<Mode>('select');
  const [direction, setDirection] = useState<'A_TO_B' | 'B_TO_A' | 'BOTH'>('BOTH');
  const [selected, setSelected] = useState<{ kind: 'line' | 'area'; id: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [snapshotKey, setSnapshotKey] = useState(Date.now());
  const [busy, setBusy] = useState(false);

  // name/prompt modal for a newly drawn shape
  const [pending, setPending] = useState<{ kind: 'line' | 'area'; points: [number, number][] } | null>(null);
  const [pendingName, setPendingName] = useState('');

  // inline edit of a selected shape
  const [editingName, setEditingName] = useState('');
  const [editingEnabled, setEditingEnabled] = useState(true);

  const fetchCameras = useCallback(async () => {
    const res = await api.getCameras({ size: 100 });
    setCameras(res.items);
    if (!selectedCameraId && res.items.length > 0) setSelectedCameraId(res.items[0].id);
  }, [selectedCameraId]);

  const fetchZones = useCallback(async () => {
    if (!selectedCameraId) return;
    setLoading(true);
    try {
      const [l, a] = await Promise.all([api.getLines(selectedCameraId), api.getAreas(selectedCameraId)]);
      setLines(l);
      setAreas(a);
    } finally {
      setLoading(false);
    }
  }, [selectedCameraId]);

  useEffect(() => { fetchCameras(); }, [fetchCameras]);
  useEffect(() => { fetchZones(); setSelected(null); }, [fetchZones]);

  useEffect(() => {
    if (!selected) { setEditingName(''); return; }
    const item = selected.kind === 'line'
      ? lines.find((l) => l.id === selected.id)
      : areas.find((a) => a.id === selected.id);
    if (item) { setEditingName(item.name); setEditingEnabled(item.enabled); }
  }, [selected, lines, areas]);

  const handleCameraChange = (id: number) => {
    setSelectedCameraId(id);
    setSearchParams({ camera: id.toString() });
    setSnapshotKey(Date.now());
  };

  // ---- drawing completion (opens a small name prompt) ------------------
  const onDrawLine = (points: [number, number][]) => {
    setPending({ kind: 'line', points });
    setPendingName('خط ' + fa(lines.length + 1));
  };
  const onDrawArea = (points: [number, number][]) => {
    setPending({ kind: 'area', points });
    setPendingName('منطقه ' + fa(areas.length + 1));
  };

  const commitPending = async () => {
    if (!pending || !selectedCameraId || !pendingName.trim()) return;
    const name = pendingName.trim();
    setBusy(true);
    try {
      if (pending.kind === 'line') {
        const [[x1, y1], [x2, y2]] = pending.points;
        await api.createLine(selectedCameraId, {
          name, x1, y1, x2, y2, direction, color: '#22c55e', enabled: true,
        });
      } else {
        await api.createArea(selectedCameraId, {
          name, points: pending.points, color: '#3b82f6', enabled: true,
        });
      }
      setPending(null);
      setPendingName('');
      setMode('select');
      await fetchZones();
    } finally {
      setBusy(false);
    }
  };

  // ---- dragging stored shapes -----------------------------------------
  const onMoveLine = async (id: number, points: [number, number][]) => {
    if (!selectedCameraId) return;
    // optimistic update
    setLines((prev) =>
      prev.map((l) => (l.id === id ? { ...l, x1: points[0][0], y1: points[0][1], x2: points[1][0], y2: points[1][1] } : l))
    );
    await api.updateLine(selectedCameraId, id, {
      x1: points[0][0], y1: points[0][1], x2: points[1][0], y2: points[1][1],
    });
  };

  const onMoveArea = async (id: number, points: [number, number][]) => {
    if (!selectedCameraId) return;
    setAreas((prev) => prev.map((a) => (a.id === id ? { ...a, points } : a)));
    await api.updateArea(selectedCameraId, id, { points });
  };

  // ---- selected shape edit / delete -----------------------------------
  const saveSelected = async () => {
    if (!selected || !selectedCameraId) return;
    setBusy(true);
    try {
      if (selected.kind === 'line') {
        await api.updateLine(selectedCameraId, selected.id, { name: editingName.trim(), enabled: editingEnabled });
      } else {
        await api.updateArea(selectedCameraId, selected.id, { name: editingName.trim(), enabled: editingEnabled });
      }
      await fetchZones();
    } finally {
      setBusy(false);
    }
  };

  const deleteSelected = async () => {
    if (!selected || !selectedCameraId) return;
    if (!window.confirm('این مورد حذف شود؟')) return;
    setBusy(true);
    try {
      if (selected.kind === 'line') await api.deleteLine(selectedCameraId, selected.id);
      else await api.deleteArea(selectedCameraId, selected.id);
      setSelected(null);
      await fetchZones();
    } finally {
      setBusy(false);
    }
  };

  const selectedItem = selected
    ? selected.kind === 'line'
      ? lines.find((l) => l.id === selected.id)
      : areas.find((a) => a.id === selected.id)
    : null;

  const backgroundUrl = selectedCameraId ? api.getCameraSnapshotUrl(selectedCameraId) : null;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">منطقه‌ها و خطوط شمارش</h1>
          <p className="text-gray-500 mt-1">روی تصویر دوربین خط و منطقه بکشید</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500 whitespace-nowrap">دوربین:</label>
          <select
            value={selectedCameraId || ''}
            onChange={(e) => handleCameraChange(parseInt(e.target.value))}
            className="input-field w-48"
          >
            <option value="">انتخاب کنید</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <button onClick={() => { setSnapshotKey(Date.now()); fetchZones(); }} className="p-2 rounded-lg text-gray-500 hover:bg-gray-100" aria-label="بارگذاری مجدد تصویر">
            <ArrowPathIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      {!selectedCameraId ? (
        <div className="card">
          <div className="empty-state h-64">
            <RectangleStackIcon className="empty-state-icon w-16 h-16" />
            <h3 className="empty-state-title">دوربین انتخاب نشده</h3>
            <p className="empty-state-description">برای شروع یک دوربین انتخاب کنید</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Canvas + toolbar */}
          <div className="lg:col-span-2 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
                <ToolButton active={mode === 'select'} onClick={() => setMode('select')} icon={CursorArrowRaysIcon} label="انتخاب" />
                <ToolButton active={mode === 'line'} onClick={() => setMode('line')} icon={MinusIcon} label="خط" />
                <ToolButton active={mode === 'area'} onClick={() => setMode('area')} icon={RectangleStackIcon} label="منطقه" />
              </div>
              {mode === 'line' && (
                <select value={direction} onChange={(e) => setDirection(e.target.value as any)} className="input-field w-40">
                  <option value="BOTH">هر دو جهت</option>
                  <option value="A_TO_B">A به B</option>
                  <option value="B_TO_A">B به A</option>
                </select>
              )}
            </div>

            <ZoneCanvas
              key={snapshotKey}
              backgroundUrl={backgroundUrl}
              lines={lines}
              areas={areas}
              mode={mode}
              selected={selected}
              onSelect={setSelected}
              onDrawLine={onDrawLine}
              onDrawArea={onDrawArea}
              onMoveLine={onMoveLine}
              onMoveArea={onMoveArea}
            />
            <p className="text-xs text-gray-400">
              نکته: عبور افراد از خط در مرکز پایین (پا) فرد شمارش می‌شود. برای ویرایش نقاط، حالت «انتخاب» را بزنید و دسته‌ها را بکشید.
            </p>
          </div>

          {/* Side panel */}
          <div className="space-y-4">
            {selectedItem && (
              <div className="card p-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  ویرایش {selected?.kind === 'line' ? 'خط' : 'منطقه'}
                </h3>
                <div>
                  <label className="label-field">نام</label>
                  <input value={editingName} onChange={(e) => setEditingName(e.target.value)} className="input-field" />
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={editingEnabled} onChange={(e) => setEditingEnabled(e.target.checked)} className="w-4 h-4 rounded" />
                  فعال
                </label>
                <div className="flex gap-2">
                  <button onClick={saveSelected} disabled={busy} className="btn-primary btn-sm flex-1">
                    <CheckIcon className="w-4 h-4 me-1" />
                    ذخیره
                  </button>
                  <button onClick={deleteSelected} disabled={busy} className="btn-outline btn-sm text-red-600">
                    <TrashIcon className="w-4 h-4 me-1" />
                    حذف
                  </button>
                </div>
              </div>
            )}

            <div className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">خطوط ({fa(lines.length)})</h3>
                <button onClick={() => setMode('line')} className="p-1 text-blue-600 hover:bg-blue-50 rounded" aria-label="افزودن خط">
                  <PlusIcon className="w-5 h-5" />
                </button>
              </div>
              {lines.length === 0 ? (
                <p className="text-xs text-gray-400 py-2">خطی رسم نشده است</p>
              ) : (
                <ul className="space-y-1">
                  {lines.map((l) => (
                    <li key={l.id}>
                      <button
                        onClick={() => { setSelected({ kind: 'line', id: l.id }); setMode('select'); }}
                        className={cn(
                          'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-start',
                          selected?.kind === 'line' && selected.id === l.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                        )}
                      >
                        <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: l.color }} />
                        <span className="flex-1 truncate">{l.name}</span>
                        <span className="text-xs text-gray-400">
                          {l.direction === 'A_TO_B' ? 'A→B' : l.direction === 'B_TO_A' ? 'B→A' : 'هر دو'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">مناطق ({fa(areas.length)})</h3>
                <button onClick={() => setMode('area')} className="p-1 text-blue-600 hover:bg-blue-50 rounded" aria-label="افزودن منطقه">
                  <PlusIcon className="w-5 h-5" />
                </button>
              </div>
              {areas.length === 0 ? (
                <p className="text-xs text-gray-400 py-2">منطقه‌ای رسم نشده است</p>
              ) : (
                <ul className="space-y-1">
                  {areas.map((a) => (
                    <li key={a.id}>
                      <button
                        onClick={() => { setSelected({ kind: 'area', id: a.id }); setMode('select'); }}
                        className={cn(
                          'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-start',
                          selected?.kind === 'area' && selected.id === a.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
                        )}
                      >
                        <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: a.color }} />
                        <span className="flex-1 truncate">{a.name}</span>
                        <span className="text-xs text-gray-400">{fa(a.points.length)} نقطه</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {loading && <p className="text-xs text-gray-400 text-center">در حال بارگذاری…</p>}
          </div>
        </div>
      )}

      {/* name prompt for a freshly drawn shape */}
      {pending && (
        <div className="modal-overlay" onClick={() => setPending(null)} role="dialog" aria-modal="true">
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="card-header flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                نام {pending.kind === 'line' ? 'خط' : 'منطقه'} جدید
              </h2>
              <button onClick={() => setPending(null)} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <div className="card-body space-y-4">
              <div>
                <label className="label-field">نام</label>
                <input
                  autoFocus
                  value={pendingName}
                  onChange={(e) => setPendingName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && commitPending()}
                  className="input-field"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setPending(null)} className="btn-secondary">انصراف</button>
                <button onClick={commitPending} disabled={busy || !pendingName.trim()} className="btn-primary">
                  {busy ? 'در حال ذخیره…' : 'ذخیره'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ToolButton({
  active, onClick, icon: Icon, label,
}: {
  active: boolean; onClick: () => void; icon: React.ComponentType<{ className?: string }>; label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
        active ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
      )}
      aria-pressed={active}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}
