import { useEffect, useRef, useState } from 'react';
import api from '@/api/client';
import { type LiveCount } from '@/api/types';

/**
 * Live counts for every camera.
 *
 * Opens the backend `/ws/counts` socket, which pushes one message per counted
 * crossing, so the dashboard updates without a page refresh. The socket sends a
 * `snapshot` first, then `count` messages. A slow poll runs alongside it as a
 * safety net: if the socket cannot connect (proxy, sleeping laptop) the UI still
 * advances, and the poll also refreshes totals that the socket does not carry.
 *
 * `eventTick` increments on every pushed event so callers can refetch
 * aggregates (today's totals) at a throttled rate instead of per event.
 */
export function useLiveCounts(pollMs = 15000) {
  const [live, setLive] = useState<Record<number, LiveCount>>({});
  const [eventTick, setEventTick] = useState(0);
  const [connected, setConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const closedByUs = useRef(false);
  const retryRef = useRef(0);
  const tickPending = useRef<ReturnType<typeof setTimeout> | null>(null);

  // -- REST polling (initial load + safety net) -------------------------
  useEffect(() => {
    let cancelled = false;

    const pull = async () => {
      try {
        const data = await api.getLiveCounts();
        if (!cancelled) setLive(Object.fromEntries(data.map((c) => [c.camera_id, c])));
      } catch {
        /* silent: next tick retries */
      }
    };

    pull();
    const id = window.setInterval(pull, pollMs);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [pollMs]);

  // -- WebSocket push ---------------------------------------------------
  useEffect(() => {
    closedByUs.current = false;

    const bumpTick = () => {
      // Coalesce bursts: one aggregate refetch per 2s at most.
      if (tickPending.current) return;
      tickPending.current = setTimeout(() => {
        tickPending.current = null;
        setEventTick((n) => n + 1);
      }, 2000);
    };

    const connect = () => {
      let socket: WebSocket;
      try {
        socket = api.createWebSocket('/ws/counts');
      } catch {
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setConnected(true);
      };

      socket.onmessage = (msg) => {
        try {
          const payload = JSON.parse(msg.data);
          if (payload?.type === 'snapshot') {
            // counts_snapshot() emits camera_summary(): {in, out, total, occupancy}
            const per = payload.data?.per_camera ?? [];
            setLive((prev) => {
              const next = { ...prev };
              for (const cam of per) {
                if (cam?.camera_id == null) continue;
                const existing = next[cam.camera_id];
                const totalIn = cam.in ?? 0;
                const totalOut = cam.out ?? 0;
                next[cam.camera_id] = {
                  ...(existing ?? ({ camera_id: cam.camera_id } as LiveCount)),
                  camera_id: cam.camera_id,
                  camera_name: existing?.camera_name ?? '',
                  current_count: totalIn - totalOut,
                  total_in: totalIn,
                  total_out: totalOut,
                };
              }
              return next;
            });
            bumpTick();
            return;
          }

          if (payload?.type === 'count' && payload.data) {
            const ev = payload.data;
            const camId = ev.camera_id;
            if (camId == null) return;
            const isIn = String(ev.direction ?? '').toUpperCase() === 'IN';
            setLive((prev) => {
              const cur = prev[camId];
              const base = cur ?? ({
                camera_id: camId,
                camera_name: ev.camera_name ?? '',
                zone_id: null,
                zone_name: null,
                current_count: 0,
                total_in: 0,
                total_out: 0,
                last_event: null,
              } as LiveCount);
              const totalIn = base.total_in + (isIn ? 1 : 0);
              const totalOut = base.total_out + (isIn ? 0 : 1);
              return {
                ...prev,
                [camId]: {
                  ...base,
                  camera_name: ev.camera_name || base.camera_name,
                  total_in: totalIn,
                  total_out: totalOut,
                  current_count: totalIn - totalOut,
                  last_event: ev,
                },
              };
            });
            bumpTick();
          }
        } catch {
          /* ignore malformed frames */
        }
      };

      socket.onclose = () => {
        setConnected(false);
        socketRef.current = null;
        if (closedByUs.current) return;
        // Backoff 1s, 2s, 4s ... capped at 15s.
        retryRef.current = Math.min(retryRef.current + 1, 4);
        const delay = Math.min(1000 * 2 ** (retryRef.current - 1), 15000);
        window.setTimeout(() => {
          if (!closedByUs.current) connect();
        }, delay);
      };

      socket.onerror = () => {
        try {
          socket.close();
        } catch {
          /* noop */
        }
      };
    };

    connect();

    return () => {
      closedByUs.current = true;
      if (tickPending.current) {
        clearTimeout(tickPending.current);
        tickPending.current = null;
      }
      try {
        socketRef.current?.close();
      } catch {
        /* noop */
      }
      socketRef.current = null;
    };
  }, []);

  return { live, eventTick, connected };
}
