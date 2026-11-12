import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cn, fa } from '../lib/utils';
import type { Line, Area, LineCreate, AreaCreate } from '../api/types';

type DragHandle = { kind: 'line' | 'area'; id: number; index: number };

interface ZoneCanvasProps {
  /** URL for the camera snapshot image (may include ?token=). */
  backgroundUrl: string | null;
  lines: Line[];
  areas: Area[];
  mode: 'select' | 'line' | 'area';
  selected: { kind: 'line' | 'area'; id: number } | null;
  onSelect: (sel: { kind: 'line' | 'area'; id: number } | null) => void;
  /** Committed when the user finishes drawing a new line (2 points). */
  onDrawLine?: (points: [number, number][]) => void;
  /** Committed when the user finishes drawing a new area (3+ points). */
  onDrawArea?: (points: [number, number][]) => void;
  /** Called after a stored line/area was dragged. */
  onMoveLine?: (id: number, points: [number, number][]) => void;
  onMoveArea?: (id: number, points: [number, number][]) => void;
  className?: string;
}

interface Point {
  x: number; // normalized 0..1
  y: number;
}

/**
 * Drawing surface for counting lines and areas over a camera snapshot.
 * Port of the PyQt ZoneEditor canvas: click-to-draw with a live rubber band,
 * draggable vertex handles, and normalized (0..1) coordinates so a zone
 * survives any snapshot resolution.
 */
export function ZoneCanvas({
  backgroundUrl,
  lines,
  areas,
  mode,
  selected,
  onSelect,
  onDrawLine,
  onDrawArea,
  onMoveLine,
  onMoveArea,
  className,
}: ZoneCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1, h: 1 });
  const [draft, setDraft] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [dragging, setDragging] = useState<DragHandle | null>(null);
  const [imgFailed, setImgFailed] = useState(false);

  // Track the rendered image box so pointer coords map to 0..1 correctly.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth || 1, h: el.clientHeight || 1 });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth || 1, h: el.clientHeight || 1 });
    return () => ro.disconnect();
  }, []);

  // Reset any in-progress drawing when the tool changes.
  useEffect(() => {
    setDraft([]);
    setCursor(null);
  }, [mode]);

  const toNorm = useCallback(
    (e: React.PointerEvent): Point => {
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) };
    },
    []
  );

  const px = useCallback((n: number, axis: 'x' | 'y') => n * (axis === 'x' ? size.w : size.h), [size]);

  // ---- pointer handlers on the canvas ---------------------------------
  const handleCanvasPointerMove = (e: React.PointerEvent) => {
    if (dragging) {
      const p = toNorm(e);
      if (dragging.kind === 'line') {
        const line = lines.find((l) => l.id === dragging.id);
        if (!line) return;
        const pts: [number, number][] = [
          [line.x1, line.y1],
          [line.x2, line.y2],
        ];
        pts[dragging.index] = [p.x, p.y];
        onMoveLine?.(line.id, pts);
      } else {
        const area = areas.find((a) => a.id === dragging.id);
        if (!area) return;
        const pts = area.points.map((q) => [q[0], q[1]] as [number, number]);
        pts[dragging.index] = [p.x, p.y];
        onMoveArea?.(area.id, pts);
      }
      return;
    }
    if (mode !== 'select') setCursor(toNorm(e));
  };

  const handleCanvasClick = (e: React.PointerEvent) => {
    if (mode === 'select') {
      onSelect(null);
      return;
    }
    const p = toNorm(e);
    if (mode === 'line') {
      const next = [...draft, p];
      if (next.length === 2) {
        onDrawLine?.([
          [next[0].x, next[0].y],
          [next[1].x, next[1].y],
        ]);
        setDraft([]);
      } else {
        setDraft(next);
      }
    } else {
      setDraft([...draft, p]);
    }
  };

  const finishArea = () => {
    if (draft.length >= 3) {
      onDrawArea?.(draft.map((p) => [p.x, p.y]));
    }
    setDraft([]);
  };

  const handleDoubleClick = () => {
    if (mode === 'area') finishArea();
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDraft([]);
        onSelect(null);
      }
      if (e.key === 'Enter' && mode === 'area') finishArea();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, draft]);

  const selectedLine = useMemo(
    () => (selected?.kind === 'line' ? lines.find((l) => l.id === selected.id) : undefined),
    [selected, lines]
  );
  const selectedArea = useMemo(
    () => (selected?.kind === 'area' ? areas.find((a) => a.id === selected.id) : undefined),
    [selected, areas]
  );


  return (
    <div className={cn('space-y-2', className)}>
      <div
        ref={containerRef}
        className={cn(
          'relative w-full aspect-video rounded-xl overflow-hidden bg-gray-900 select-none',
          mode === 'select' ? 'cursor-default' : 'cursor-crosshair'
        )}
        onPointerMove={handleCanvasPointerMove}
        onPointerDown={(e) => {
          // A handle click starts a drag; don't also start drawing.
          if (dragging) return;
          handleCanvasClick(e);
        }}
        onDoubleClick={handleDoubleClick}
        role="application"
        aria-label="بوم رسم خطوط و مناطق شمارش"
      >
        {backgroundUrl && !imgFailed ? (
          <img
            src={backgroundUrl}
            alt="تصویر دوربین"
            className="absolute inset-0 w-full h-full object-fill pointer-events-none"
            onError={() => setImgFailed(true)}
            draggable={false}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500 gap-1">
            <span className="text-sm">تصویری از دوربین در دسترس نیست</span>
            <span className="text-xs text-gray-600">می‌توانید مناطق را روی این بوم رسم کنید</span>
          </div>
        )}

        <svg className="absolute inset-0 w-full h-full" viewBox={`0 0 ${size.w} ${size.h}`} preserveAspectRatio="none">
          {/* stored lines */}
          {lines.map((l) => {
            const isSel = selected?.kind === 'line' && selected.id === l.id;
            const x1 = px(l.x1, 'x'), y1 = px(l.y1, 'y'), x2 = px(l.x2, 'x'), y2 = px(l.y2, 'y');
            return (
              <g key={`line-${l.id}`}>
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={l.color}
                  strokeWidth={isSel ? 4 : 3}
                  strokeDasharray={l.enabled ? undefined : '6 4'}
                  opacity={l.enabled ? 1 : 0.5}
                />
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="transparent"
                  strokeWidth={16}
                  className="cursor-pointer"
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    onSelect({ kind: 'line', id: l.id });
                  }}
                />
                <DirectionalArrow x1={x1} y1={y1} x2={x2} y2={y2} color={l.color} direction={l.direction} />
                {isSel && (
                  <>
                    {/* Endpoint labels: A is the first point drawn, B the second.
                        A_TO_B counts crossings moving from the A side to the B
                        side, so showing which dot is which makes the direction
                        readable instead of guessable. */}
                    <circle cx={x1} cy={y1} r={7} fill="#f59e0b" stroke="#fff" strokeWidth={2} className="cursor-grab"
                      onPointerDown={(e) => { e.stopPropagation(); setDragging({ kind: 'line', id: l.id, index: 0 }); }} />
                    <circle cx={x2} cy={y2} r={7} fill="#38bdf8" stroke="#fff" strokeWidth={2} className="cursor-grab"
                      onPointerDown={(e) => { e.stopPropagation(); setDragging({ kind: 'line', id: l.id, index: 1 }); }} />
                    <text
                      x={x1} y={y1} textAnchor="middle" dominantBaseline="central"
                      fontSize={10} fontWeight={700} fill="#1f2937"
                      pointerEvents="none"
                    >A</text>
                    <text
                      x={x2} y={y2} textAnchor="middle" dominantBaseline="central"
                      fontSize={10} fontWeight={700} fill="#082f49"
                      pointerEvents="none"
                    >B</text>
                  </>
                )}
              </g>
            );
          })}

          {/* stored areas */}
          {areas.map((a) => {
            const isSel = selected?.kind === 'area' && selected.id === a.id;
            const pts = a.points.map((p) => `${px(p[0], 'x')},${px(p[1], 'y')}`).join(' ');
            return (
              <g key={`area-${a.id}`}>
                <polygon
                  points={pts}
                  fill={a.color}
                  fillOpacity={a.enabled ? 0.22 : 0.1}
                  stroke={a.color}
                  strokeWidth={isSel ? 3 : 2}
                  strokeDasharray={a.enabled ? undefined : '6 4'}
                  className="cursor-pointer"
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    onSelect({ kind: 'area', id: a.id });
                  }}
                />
                {isSel &&
                  a.points.map((p, i) => (
                    <circle
                      key={i}
                      cx={px(p[0], 'x')}
                      cy={px(p[1], 'y')}
                      r={7}
                      fill="#f59e0b"
                      stroke="#fff"
                      strokeWidth={2}
                      className="cursor-grab"
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        setDragging({ kind: 'area', id: a.id, index: i });
                      }}
                    />
                  ))}
              </g>
            );
          })}

          {/* live draft for a line in progress */}
          {mode === 'line' && draft.length === 1 && cursor && (
            <>
              <line
                x1={px(draft[0].x, 'x')} y1={px(draft[0].y, 'y')}
                x2={px(cursor.x, 'x')} y2={px(cursor.y, 'y')}
                stroke="#eab308" strokeWidth={2} strokeDasharray="6 4"
              />
              <circle cx={px(cursor.x, 'x')} cy={px(cursor.y, 'y')} r={7} fill="#38bdf8" stroke="#fff" strokeWidth={2} opacity={0.85} />
              <text
                x={px(cursor.x, 'x')} y={px(cursor.y, 'y')}
                textAnchor="middle" dominantBaseline="central"
                fontSize={10} fontWeight={700} fill="#082f49" pointerEvents="none" opacity={0.9}
              >B</text>
            </>
          )}
          {mode === 'line' && draft.length === 1 && (
            <>
              <circle cx={px(draft[0].x, 'x')} cy={px(draft[0].y, 'y')} r={7} fill="#f59e0b" stroke="#fff" strokeWidth={2} />
              <text
                x={px(draft[0].x, 'x')} y={px(draft[0].y, 'y')}
                textAnchor="middle" dominantBaseline="central"
                fontSize={10} fontWeight={700} fill="#1f2937" pointerEvents="none"
              >A</text>
            </>
          )}

          {/* live draft for an area in progress */}
          {mode === 'area' && draft.length > 0 && (
            <polyline
              points={[...draft.map((p) => `${px(p.x, 'x')},${px(p.y, 'y')}`), cursor ? `${px(cursor.x, 'x')},${px(cursor.y, 'y')}` : ''].join(' ')}
              fill="none"
              stroke="#eab308"
              strokeWidth={2}
              strokeDasharray="6 4"
            />
          )}
          {mode === 'area' &&
            draft.map((p, i) => (
              <circle key={i} cx={px(p.x, 'x')} cy={px(p.y, 'y')} r={5} fill="#eab308" stroke="#fff" strokeWidth={1} />
            ))}
        </svg>

        {/* floating hint */}
        <div className="absolute bottom-2 start-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
          {mode === 'line' && (draft.length === 0 ? 'برای رسم خط، نقطه A را کلیک کنید' : 'نقطه B را کلیک کنید')}
          {mode === 'area' && (draft.length < 3 ? `رئوس را کلیک کنید (${fa(draft.length)})` : 'دوبار کلیک یا Enter برای بستن')}
          {mode === 'select' && 'برای جابه‌جایی، یک خط یا منطقه را انتخاب کنید'}
        </div>
      </div>

      {/* action row */}
      <div className="flex flex-wrap items-center gap-2">
        {mode === 'area' && draft.length >= 3 && (
          <button onClick={finishArea} className="btn-primary btn-sm">
            بستن منطقه ({fa(draft.length)} نقطه)
          </button>
        )}
        {(draft.length > 0) && (
          <button onClick={() => setDraft([])} className="btn-outline btn-sm">
            لغو رسم
          </button>
        )}
        {(selectedLine || selectedArea) && (
          <span className="text-xs text-gray-500">
            انتخاب‌شده: {selectedLine?.name || selectedArea?.name}
            {selectedLine && ` (${selectedLine.direction === 'A_TO_B' ? 'A→B' : selectedLine.direction === 'B_TO_A' ? 'B→A' : 'هر دو'})`}
          </span>
        )}
      </div>
    </div>
  );
}

/** Perpendicular arrow marking the counted walking direction (like the PyQt editor).
 *
 * The arrow is drawn offset to one side of the line rather than on top of it, so
 * A_TO_B and B_TO_A never overlap and each clearly shows which side a person
 * must move towards. A vertical line therefore gets a left or right arrow and a
 * horizontal line an up or down one, matching the engine's normal convention:
 * the sign of the cross product of the line vector and the movement.
 */
function DirectionalArrow({
  x1, y1, x2, y2, color, direction,
}: {
  x1: number; y1: number; x2: number; y2: number; color: string; direction: string;
}) {
  const vx = x2 - x1;
  const vy = y2 - y1;
  const norm = Math.hypot(vx, vy);
  if (norm < 1e-6) return null;
  // Unit normal to the line; crossing from -normal to +normal is A_TO_B (IN).
  const nx = -vy / norm;
  const ny = vx / norm;
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;

  const len = Math.max(18, Math.min(54, norm * 0.16));
  const head = Math.max(7, len * 0.32);
  // Push the arrow clear of the line so the two directions cannot overlap.
  const offset = 12;

  /** Arrow pointing towards the side a crossing must move into. */
  const arrow = (sign: 1 | -1) => {
    const cx = mx + nx * offset * sign;
    const cy = my + ny * offset * sign;
    const sx = cx - nx * (len / 2) * sign;
    const sy = cy - ny * (len / 2) * sign;
    const ex = cx + nx * (len / 2) * sign;
    const ey = cy + ny * (len / 2) * sign;
    // Arrowhead: two points behind the tip, spread along the line direction.
    const ux = vx / norm;
    const uy = vy / norm;
    const bx = ex - nx * head * sign;
    const by = ey - ny * head * sign;
    const p1 = `${bx + ux * head * 0.55},${by + uy * head * 0.55}`;
    const p2 = `${bx - ux * head * 0.55},${by - uy * head * 0.55}`;
    return (
      <g key={sign}>
        <line x1={sx} y1={sy} x2={ex} y2={ey} stroke={color} strokeWidth={2.5} strokeLinecap="round" />
        <polygon points={`${ex},${ey} ${p1} ${p2}`} fill={color} />
      </g>
    );
  };

  // BOTH counts crossings in either direction, so show an arrow each way;
  // a single arrow would suggest only one side is counted.
  const signs: Array<1 | -1> = direction === 'BOTH' ? [1, -1] : [direction === 'B_TO_A' ? -1 : 1];

  return (
    <g pointerEvents="none">
      {signs.map((s) => arrow(s))}
      {direction === 'BOTH' && (
        <text
          x={mx}
          y={my}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={9}
          fill={color}
          style={{ paintOrder: 'stroke', stroke: '#000', strokeWidth: 2.5, strokeOpacity: 0.55 }}
        >
          هر دو
        </text>
      )}
    </g>
  );
}

export type { LineCreate, AreaCreate };
