import React, { useState, useEffect, useRef, useCallback } from 'react';

const API = `${window.location.protocol}//${window.location.hostname}:${window.location.port || 8000}`;

function TelemetryPanel({ ws }) {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [slowTools, setSlowTools] = useState([]);
  const [errorHotspots, setErrorHotspots] = useState([]);
  const [hourly, setHourly] = useState([]);
  const [liveEvents, setLiveEvents] = useState([]);
  const [tab, setTab] = useState('live');
  const [limit, setLimit] = useState(20);
  const liveRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [s, h, st, eh, hr] = await Promise.all([
        fetch(`${API}/telemetry/stats`).then(r => r.json()),
        fetch(`${API}/telemetry/history?limit=${limit}`).then(r => r.json()),
        fetch(`${API}/telemetry/slow-tools`).then(r => r.json()),
        fetch(`${API}/telemetry/error-hotspots`).then(r => r.json()),
        fetch(`${API}/telemetry/hourly`).then(r => r.json()),
      ]);
      setStats(s);
      setHistory(h.history || h);
      setSlowTools(st.slow_tools || st);
      setErrorHotspots(eh.error_hotspots || eh);
      setHourly(hr.hourly || hr);
    } catch (e) {
      console.error('Telemetry fetch error:', e);
    }
  }, [limit]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (!ws) return;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'telemetry_event') {
          setLiveEvents(prev => [data.payload, ...prev].slice(0, 100));
        }
      } catch (e) {}
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ type: 'subscribe_telemetry' }));
    return () => {
      ws.removeEventListener('message', handler);
      ws.send(JSON.stringify({ type: 'unsubscribe_telemetry' }));
    };
  }, [ws]);

  useEffect(() => {
    if (liveRef.current) liveRef.current.scrollTop = 0;
  }, [liveEvents]);

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Telemetry Dashboard</h2>

      {/* Tab bar */}
      <div style={styles.tabBar}>
        {['live', 'stats', 'history', 'slow', 'errors', 'hourly'].map(t => (
          <button key={t} style={styles.tab(tab === t)} onClick={() => setTab(t)}>
            {t === 'live' ? 'Live' : t === 'stats' ? 'Stats' : t === 'history' ? 'History' : t === 'slow' ? 'Slow Tools' : t === 'errors' ? 'Error Hotspots' : 'Hourly'}
          </button>
        ))}
      </div>

      <div style={styles.content}>
        {tab === 'live' && (
          <div ref={liveRef} style={styles.liveFeed}>
            {liveEvents.length === 0 && <div style={styles.empty}>Waiting for live events...</div>}
            {liveEvents.map((ev, i) => (
              <div key={i} style={styles.liveRow}>
                <span style={styles.liveTime}>{ev.timestamp ? ev.timestamp.slice(11, 19) : ''}</span>
                <span style={styles.liveTool}>{ev.tool_name}</span>
                <span style={{ ...styles.liveBadge, background: ev.success ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,68,0.2)', color: ev.success ? '#00ff88' : '#ff4444' }}>
                  {ev.success ? 'OK' : 'ERR'}
                </span>
                <span style={styles.liveDuration}>{ev.duration_ms?.toFixed(0)}ms</span>
                {ev.session_id && <span style={styles.liveSession}>{ev.session_id.slice(0, 8)}</span>}
              </div>
            ))}
          </div>
        )}

        {tab === 'stats' && stats && (
          <div style={styles.statsGrid}>
            <div style={styles.statCard}>
              <div style={styles.statValue}>{stats.total_calls || 0}</div>
              <div style={styles.statLabel}>Total Calls</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statValue}>{stats.unique_tools || 0}</div>
              <div style={styles.statLabel}>Unique Tools</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statValue}>{stats.success_rate ? (stats.success_rate * 100).toFixed(1) + '%' : '0%'}</div>
              <div style={styles.statLabel}>Success Rate</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statValue}>{stats.avg_duration_ms ? stats.avg_duration_ms.toFixed(0) : 0}ms</div>
              <div style={styles.statLabel}>Avg Duration</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statValue}>{stats.error_count || 0}</div>
              <div style={styles.statLabel}>Errors</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statValue}>{stats.active_sessions || 0}</div>
              <div style={styles.statLabel}>Active Sessions</div>
            </div>
            {stats.per_tool && (
              <div style={{ ...styles.statCard, gridColumn: '1 / -1' }}>
                <div style={styles.statLabel}>Per Tool</div>
                {Object.entries(stats.per_tool).slice(0, 20).map(([tool, data]) => (
                  <div key={tool} style={styles.toolRow}>
                    <span>{tool}</span>
                    <span>{data.calls} calls, {data.avg_duration_ms?.toFixed(0) || '?'}ms</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'history' && (
          <div style={styles.historyTable}>
            <div style={styles.historyHeader}>
              <span>Time</span><span>Tool</span><span>Session</span><span>Duration</span><span>Status</span>
            </div>
            {history.map((h, i) => (
              <div key={i} style={styles.historyRow(i % 2 === 0)}>
                <span>{h.timestamp ? h.timestamp.slice(11, 19) : ''}</span>
                <span>{h.tool_name}</span>
                <span style={{ fontSize: '0.7rem' }}>{h.session_id?.slice(0, 12)}</span>
                <span>{h.duration_ms?.toFixed(0)}ms</span>
                <span style={{ color: h.success ? '#00ff88' : '#ff4444' }}>{h.success ? 'OK' : 'FAIL'}</span>
              </div>
            ))}
          </div>
        )}

        {tab === 'slow' && (
          <div>
            {slowTools.length === 0 && <div style={styles.empty}>No slow tools detected</div>}
            {slowTools.map((st, i) => (
              <div key={i} style={styles.slowRow}>
                <span style={{ fontWeight: 600 }}>{st.tool_name}</span>
                <span style={styles.statLabel}>avg {st.avg_duration_ms?.toFixed(0)}ms</span>
                <span style={styles.statLabel}>max {st.max_duration_ms?.toFixed(0)}ms</span>
                <span style={styles.statLabel}>{st.call_count} calls</span>
              </div>
            ))}
          </div>
        )}

        {tab === 'errors' && (
          <div>
            {errorHotspots.length === 0 && <div style={styles.empty}>No error hotspots</div>}
            {errorHotspots.map((eh, i) => (
              <div key={i} style={styles.slowRow}>
                <span style={{ fontWeight: 600 }}>{eh.tool_name}</span>
                <span style={{ color: '#ff4444' }}>{eh.error_count} errors</span>
                <span style={styles.statLabel}>{eh.last_error?.slice(0, 80)}</span>
              </div>
            ))}
          </div>
        )}

        {tab === 'hourly' && (
          <div>
            {hourly.length === 0 && <div style={styles.empty}>No hourly data yet</div>}
            {hourly.map((h, i) => (
              <div key={i} style={styles.slowRow}>
                <span style={{ fontWeight: 600 }}>{h.hour || h.period}</span>
                <span>{h.calls} calls</span>
                <span>{h.errors} errors</span>
                <span>{h.avg_duration_ms?.toFixed(0)}ms avg</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: { padding: 16, height: '100%', display: 'flex', flexDirection: 'column' },
  title: { color: '#00d4ff', margin: '0 0 12px 0', fontSize: '1.1rem' },
  tabBar: { display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' },
  tab: (active) => ({
    padding: '6px 14px', borderRadius: 16, border: 'none', cursor: 'pointer',
    fontSize: '0.75rem', fontWeight: 600,
    background: active ? '#00d4ff' : 'rgba(255,255,255,0.05)',
    color: active ? '#0a0a1a' : '#8a9aaa',
  }),
  content: { flex: 1, overflow: 'auto' },
  empty: { color: '#5a7a8a', textAlign: 'center', padding: 40 },
  liveFeed: { display: 'flex', flexDirection: 'column', gap: 2, maxHeight: '100%', overflow: 'auto' },
  liveRow: { display: 'flex', gap: 8, alignItems: 'center', padding: '3px 6px', fontSize: '0.75rem', fontFamily: 'monospace' },
  liveTime: { color: '#5a7a8a', width: 60 },
  liveTool: { flex: 1, color: '#c8d6e5' },
  liveBadge: { padding: '1px 6px', borderRadius: 8, fontSize: '0.65rem', fontWeight: 700 },
  liveDuration: { color: '#f59e0b', width: 50, textAlign: 'right' },
  liveSession: { color: '#5a7a8a', fontSize: '0.65rem', width: 60 },
  statsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 },
  statCard: { background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 12, border: '1px solid rgba(255,255,255,0.06)' },
  statValue: { fontSize: '1.5rem', fontWeight: 700, color: '#00d4ff' },
  statLabel: { fontSize: '0.7rem', color: '#5a7a8a', marginTop: 4 },
  toolRow: { display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.04)' },
  historyTable: { display: 'flex', flexDirection: 'column', gap: 1, fontSize: '0.75rem', fontFamily: 'monospace' },
  historyHeader: { display: 'flex', gap: 8, padding: '6px 8px', color: '#5a7a8a', fontWeight: 600, borderBottom: '1px solid rgba(255,255,255,0.1)' },
  historyRow: (alt) => ({ display: 'flex', gap: 8, padding: '4px 8px', background: alt ? 'rgba(255,255,255,0.02)' : 'transparent' }),
  slowRow: { display: 'flex', gap: 12, padding: '8px 12px', fontSize: '0.8rem', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.04)' },
};

export default TelemetryPanel;
