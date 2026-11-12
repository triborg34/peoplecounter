import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Check, MousePointer2, Plus, RefreshCw, Shapes, Slash, Trash2 } from 'lucide-react';
import api from '@/api/client';
import { type Area, type Camera, type Line } from '@/api/types';
import { ZoneCanvas } from '@/components/ZoneCanvas';
import { cn, fa } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Field, Input } from '@/components/ui/input';

type Mode = 'select' | 'line' | 'area';

export function ZonesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [cameraId, setCameraId] = useState<number | null>(
    searchParams.get('camera') ? parseInt(searchParams.get('camera')!) : null,
  );
  const [mode, setMode] = useState<Mode>('select');
  const [direction, setDirection] = useState<'A_TO_B' | 'B_TO_A' | 'BOTH'>('BOTH');
  const [selected, setSelected] = useState<{ kind: 'line' | 'area'; id: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [snapshotKey, setSnapshotKey] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const [pending, setPending] = useState<{ kind: 'line' | 'area'; points: [number, number][] } | null>(null);
  const [pendingName, setPendingName] = useState('');

  const [editingName, setEditingName] = useState('');
  const [editingEnabled, setEditingEnabled] = useState(true);

  const fetchCameras = useCallback(async () => {
    const res = await api.getCameras({ size: 100 });
    setCameras(res.items);
    if (!cameraId && res.items.length > 0) setCameraId(res.items[0].id);
  }, [cameraId]);

  const fetchZones = useCallback(async () => {
    if (!cameraId) return;
    setLoading(true);
    try {
      const [l, a] = await Promise.all([api.getLines(cameraId), api.getAreas(cameraId)]);
      setLines(l);
      setAreas(a);
    } catch (err: any) {
      // Previously an empty finally swallowed nothing, but a rejection here
      // aborted the caller before setLines/setAreas ran, so the canvas kept
      // showing deleted items. Surface it and keep the lists untouched.
      setError(err?.response?.data?.detail || 'خطا در بارگذاری خطوط و مناطق');
    } finally {
      setLoading(false);
    }
  }, [cameraId]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);
  useEffect(() => {
    fetchZones();
    setSelected(null);
  }, [fetchZones]);

  useEffect(() => {
    if (!selected) {
      setEditingName('');
      return;
    }
    const item = selected.kind === 'line' ? lines.find((l) => l.id === selected.id) : areas.find((a) => a.id === selected.id);
    if (item) {
      setEditingName(item.name);
      setEditingEnabled(item.enabled);
    }
    // Reflect the selected line's own direction in the toolbar, so the control
    // always shows what is stored instead of the last value picked.
    if (selected.kind === 'line') {
      const line = lines.find((l) => l.id === selected.id);
      if (line?.direction) setDirection(line.direction);
    }
  }, [selected, lines, areas]);

  function changeCamera(id: number) {
    setCameraId(id);
    setSearchParams({ camera: id.toString() });
    setSnapshotKey(Date.now());
  }

  function onDrawLine(points: [number, number][]) {
    setPending({ kind: 'line', points });
    setPendingName('خط ' + fa(lines.length + 1));
  }
  function onDrawArea(points: [number, number][]) {
    setPending({ kind: 'area', points });
    setPendingName('منطقه ' + fa(areas.length + 1));
  }

  async function commitPending() {
    if (!pending || !cameraId || !pendingName.trim()) return;
    const name = pendingName.trim();
    setBusy(true);
    try {
      if (pending.kind === 'line') {
        const [[x1, y1], [x2, y2]] = pending.points;
        await api.createLine(cameraId, { name, x1, y1, x2, y2, direction, color: '#e8a33d', enabled: true });
      } else {
        await api.createArea(cameraId, { name, points: pending.points, color: '#4ec9b0', enabled: true });
      }
      setPending(null);
      setPendingName('');
      setMode('select');
      await fetchZones();
    } finally {
      setBusy(false);
    }
  }

  async function onMoveLine(id: number, points: [number, number][]) {
    if (!cameraId) return;
    setLines((prev) => prev.map((l) => (l.id === id ? { ...l, x1: points[0][0], y1: points[0][1], x2: points[1][0], y2: points[1][1] } : l)));
    await api.updateLine(cameraId, id, { x1: points[0][0], y1: points[0][1], x2: points[1][0], y2: points[1][1] });
  }

  async function onMoveArea(id: number, points: [number, number][]) {
    if (!cameraId) return;
    setAreas((prev) => prev.map((a) => (a.id === id ? { ...a, points } : a)));
    await api.updateArea(cameraId, id, { points });
  }

  /** Changing the direction dropdown on a selected line persists immediately. */
  async function changeDirection(next: 'A_TO_B' | 'B_TO_A' | 'BOTH') {
    setDirection(next);
    if (selected?.kind === 'line' && cameraId) {
      setLines((prev) => prev.map((l) => (l.id === selected.id ? { ...l, direction: next } : l)));
      try {
        await api.updateLine(cameraId, selected.id, { direction: next });
      } catch {
        await fetchZones(); // roll back to server truth
      }
    }
  }

  async function saveSelected() {
    if (!selected || !cameraId) return;
    setBusy(true);
    try {
      if (selected.kind === 'line') {
        await api.updateLine(cameraId, selected.id, { name: editingName.trim(), enabled: editingEnabled, direction });
      } else {
        await api.updateArea(cameraId, selected.id, { name: editingName.trim(), enabled: editingEnabled });
      }
      await fetchZones();
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelected() {
    if (!selected || !cameraId) return;
    if (!window.confirm('این مورد حذف شود؟')) return;
    const target = { ...selected };
    setBusy(true);
    try {
      if (target.kind === 'line') await api.deleteLine(cameraId, target.id);
      else await api.deleteArea(cameraId, target.id);
      // Drop it locally first: the row is already gone in the database, so the
      // canvas must not keep showing it even if the refetch below fails.
      if (target.kind === 'line') setLines((prev) => prev.filter((l) => l.id !== target.id));
      else setAreas((prev) => prev.filter((a) => a.id !== target.id));
      setSelected(null);
      await fetchZones();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'خطا در حذف');
      // Re-sync with the server so the UI never diverges from the database.
      await fetchZones().catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  const selectedItem = selected ? (selected.kind === 'line' ? lines.find((l) => l.id === selected.id) : areas.find((a) => a.id === selected.id)) : null;
  const backgroundUrl = cameraId ? api.getCameraSnapshotUrl(cameraId) : null;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-lg font-bold">خطوط و مناطق شمارش</h1>
          <p className="text-sm text-muted-foreground">روی تصویر دوربین خط و منطقه بکشید</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            aria-label="انتخاب دوربین"
            value={cameraId ?? ''}
            onChange={(e) => changeCamera(parseInt(e.target.value))}
            className="h-9 w-44 rounded-field border-line-field border-input bg-field px-2 text-sm shadow-field focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <option value="">انتخاب دوربین…</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <Button variant="outline" size="icon" className="size-9" aria-label="بارگذاری مجدد تصویر" onClick={() => { setSnapshotKey(Date.now()); fetchZones(); }}>
            <RefreshCw className="size-4" strokeWidth={1.75} />
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between gap-3 rounded-control border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <span>{error}</span>
          <button type="button" className="underline" onClick={() => setError('')}>بستن</button>
        </div>
      )}

      {!cameraId ? (
        <Card>
          <CardContent className="pt-5">
            <EmptyState icon={Shapes} title="دوربین انتخاب نشده" description="برای رسم خط و منطقه، ابتدا یک دوربین انتخاب کنید." />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="space-y-3 lg:col-span-2">
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-control border-line border-border bg-card p-0.5" role="toolbar" aria-label="ابزار رسم">
                <ToolButton active={mode === 'select'} onClick={() => setMode('select')} icon={MousePointer2} label="انتخاب" />
                <ToolButton active={mode === 'line'} onClick={() => setMode('line')} icon={Slash} label="خط" />
                <ToolButton active={mode === 'area'} onClick={() => setMode('area')} icon={Shapes} label="منطقه" />
              </div>
              {mode === 'line' && (
                <select
                  aria-label="جهت شمارش خط"
                  value={direction}
                  onChange={(e) => changeDirection(e.target.value as typeof direction)}
                  className="h-9 rounded-field border-line-field border-input bg-field px-2 text-sm shadow-field focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  <option value="BOTH">هر دو جهت</option>
                  <option value="A_TO_B">A ← به → B (ورود از سمت A)</option>
                  <option value="B_TO_A">B ← به → A (ورود از سمت B)</option>
                </select>
              )}
            </div>

            <div className="overflow-hidden rounded-surface border-line border-border bg-card">
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
            </div>
            <p className="text-xs leading-5 text-muted-foreground">
              نکته: عبور افراد از خط در نقطه‌ی پایین (پا) شمارش می‌شود. برای ویرایش نقاط، حالت «انتخاب» را فعال کنید و دسته‌ها را بکشید.
            </p>
          </div>

          <div className="space-y-4">
            {selectedItem && (
              <Card>
                <CardHeader>
                  <CardTitle>ویرایش {selected?.kind === 'line' ? 'خط' : 'منطقه'}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Field label="نام" htmlFor="zone-name">
                    <Input id="zone-name" value={editingName} onChange={(e) => setEditingName(e.target.value)} />
                  </Field>
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <input type="checkbox" checked={editingEnabled} onChange={(e) => setEditingEnabled(e.target.checked)} className="size-4 accent-[var(--brand)]" />
                    فعال
                  </label>
                  <div className="flex gap-2">
                    <Button size="sm" className="flex-1" disabled={busy} onClick={saveSelected}>
                      <Check className="size-4" />
                      ذخیره
                    </Button>
                    <Button size="sm" variant="destructive" disabled={busy} onClick={deleteSelected}>
                      <Trash2 className="size-4" />
                      حذف
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            <ZoneList
              title={`خطوط (${fa(lines.length)})`}
              emptyText="خطی رسم نشده است"
              onAdd={() => setMode('line')}
              items={lines.map((l) => ({
                id: l.id,
                name: l.name,
                color: l.color,
                meta: l.direction === 'A_TO_B' ? 'A→B' : l.direction === 'B_TO_A' ? 'B→A' : 'هر دو',
                active: selected?.kind === 'line' && selected.id === l.id,
                onSelect: () => {
                  setSelected({ kind: 'line', id: l.id });
                  setMode('select');
                },
              }))}
            />

            <ZoneList
              title={`مناطق (${fa(areas.length)})`}
              emptyText="منطقه‌ای رسم نشده است"
              onAdd={() => setMode('area')}
              items={areas.map((a) => ({
                id: a.id,
                name: a.name,
                color: a.color,
                meta: `${fa(a.points.length)} نقطه`,
                active: selected?.kind === 'area' && selected.id === a.id,
                onSelect: () => {
                  setSelected({ kind: 'area', id: a.id });
                  setMode('select');
                },
              }))}
            />

            {loading && <p className="text-center text-xs text-muted-foreground">در حال بارگذاری…</p>}
          </div>
        </div>
      )}

      <Dialog
        open={!!pending}
        onOpenChange={(o) => !o && setPending(null)}
        title={pending?.kind === 'line' ? 'نام خط جدید' : 'نام منطقه جدید'}
        description="مختصات به‌صورت نرمال‌شده ذخیره می‌شود و در هر رزولوشنی درست کار می‌کند."
      >
        <div className="space-y-4">
          <Field label="نام" htmlFor="pending-name">
            <Input
              id="pending-name"
              data-autofocus
              value={pendingName}
              onChange={(e) => setPendingName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && commitPending()}
            />
          </Field>
          <div className="flex gap-2">
            <Button onClick={commitPending} disabled={busy || !pendingName.trim()}>
              {busy ? 'در حال ذخیره…' : 'ذخیره'}
            </Button>
            <Button variant="ghost" onClick={() => setPending(null)}>
              انصراف
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

function ToolButton({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: React.ComponentType<{ className?: string; strokeWidth?: number }>; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex cursor-pointer items-center gap-1.5 rounded-control px-3 py-1.5 text-sm font-medium transition-colors duration-(--motion) ease-motion',
        active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
      )}
    >
      <Icon className="size-4" strokeWidth={1.75} />
      {label}
    </button>
  );
}

interface ZoneListItem {
  id: number;
  name: string;
  color: string;
  meta: string;
  active: boolean;
  onSelect: () => void;
}

function ZoneList({ title, emptyText, items, onAdd }: { title: string; emptyText: string; items: ZoneListItem[]; onAdd: () => void }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-0">
        <CardTitle className="text-sm">{title}</CardTitle>
        <Button variant="ghost" size="icon" className="size-7" aria-label={`افزودن به ${title}`} onClick={onAdd}>
          <Plus className="size-4" strokeWidth={1.75} />
        </Button>
      </CardHeader>
      <CardContent className="pt-3">
        {items.length === 0 ? (
          <p className="py-1 text-xs text-muted-foreground">{emptyText}</p>
        ) : (
          <ul className="space-y-1">
            {items.map((it) => (
              <li key={it.id}>
                <button
                  type="button"
                  onClick={it.onSelect}
                  className={cn(
                    'flex w-full cursor-pointer items-center gap-2 rounded-control px-2 py-1.5 text-start text-sm transition-colors',
                    it.active ? 'bg-accent text-foreground' : 'text-foreground/85 hover:bg-accent/60',
                  )}
                >
                  <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: it.color }} aria-hidden />
                  <span className="flex-1 truncate">{it.name}</span>
                  <span className="text-[11px] text-muted-foreground">{it.meta}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
