import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://localhost:8000';

function PluginManager() {
  const [plugins, setPlugins] = useState([]);
  const [watcherRunning, setWatcherRunning] = useState(false);
  const [message, setMessage] = useState('');

  const fetchPlugins = useCallback(async () => {
    try {
      const res = await fetch(`${API}/plugins`);
      const data = await res.json();
      setPlugins(data.plugins || data);
    } catch (e) {
      console.error('Failed to fetch plugins:', e);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
    const interval = setInterval(fetchPlugins, 5000);
    return () => clearInterval(interval);
  }, [fetchPlugins]);

  const doAction = async (action, body) => {
    try {
      const res = await fetch(`${API}/plugins/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json();
      setMessage(data.message || data.status || 'Done');
      setTimeout(() => setMessage(''), 3000);
      fetchPlugins();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    }
  };

  const togglePlugin = async (name, enable) => {
    await doAction(`${name}/${enable ? 'enable' : 'disable'}`);
  };

  const reloadPlugin = async (name) => {
    await doAction(`${name}/reload`);
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Plugin Manager</h2>

      {message && <div style={styles.message}>{message}</div>}

      <div style={styles.actions}>
        <button style={styles.btn} onClick={() => doAction('scan')}>Scan Plugins</button>
        <button style={styles.btn} onClick={() => doAction('example')}>Create Example Plugin</button>
        <button style={{ ...styles.btn, background: watcherRunning ? '#ff4444' : '#00d4ff' }}
          onClick={async () => {
            await doAction(watcherRunning ? 'watcher/stop' : 'watcher/start');
            setWatcherRunning(!watcherRunning);
          }}>
          {watcherRunning ? 'Stop Watcher' : 'Start Watcher'}
        </button>
      </div>

      {plugins.length === 0 && <div style={styles.empty}>No plugins loaded</div>}

      <div style={styles.pluginList}>
        {plugins.map((p, i) => (
          <div key={i} style={styles.pluginCard}>
            <div style={styles.pluginHeader}>
              <span style={styles.pluginName}>{p.name || p.plugin_name || 'Unknown'}</span>
              <span style={{ ...styles.badge, background: p.enabled ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,68,0.2)', color: p.enabled ? '#00ff88' : '#ff4444' }}>
                {p.enabled ? 'Enabled' : 'Disabled'}
              </span>
              <span style={styles.pluginVersion}>{p.version || ''}</span>
            </div>
            <div style={styles.pluginDesc}>{p.description || p.metadata?.description || ''}</div>
            <div style={styles.pluginTools}>
              Tools: {(p.tools || p.tool_count || 0) > 0
                ? (p.tools || []).map(t => typeof t === 'string' ? t : t.name || t.function?.name).filter(Boolean).join(', ')
                : `${p.tool_count || 0} tools`}
            </div>
            <div style={styles.pluginActions}>
              <button style={styles.smallBtn} onClick={() => togglePlugin(p.name || p.plugin_name, !p.enabled)}>
                {p.enabled ? 'Disable' : 'Enable'}
              </button>
              <button style={styles.smallBtn} onClick={() => reloadPlugin(p.name || p.plugin_name)}>Reload</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: { padding: 16, height: '100%', display: 'flex', flexDirection: 'column' },
  title: { color: '#00d4ff', margin: '0 0 12px 0', fontSize: '1.1rem' },
  message: { background: 'rgba(0,212,255,0.15)', border: '1px solid rgba(0,212,255,0.3)', borderRadius: 8, padding: '8px 12px', fontSize: '0.8rem', marginBottom: 8, color: '#00d4ff' },
  actions: { display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' },
  btn: { padding: '6px 14px', borderRadius: 16, border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, background: '#00d4ff', color: '#0a0a1a' },
  empty: { color: '#5a7a8a', textAlign: 'center', padding: 40 },
  pluginList: { display: 'flex', flexDirection: 'column', gap: 8, overflow: 'auto' },
  pluginCard: { background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 12, border: '1px solid rgba(255,255,255,0.06)' },
  pluginHeader: { display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 },
  pluginName: { fontWeight: 600, color: '#c8d6e5', fontSize: '0.9rem' },
  badge: { padding: '1px 8px', borderRadius: 10, fontSize: '0.65rem', fontWeight: 700 },
  pluginVersion: { fontSize: '0.7rem', color: '#5a7a8a', marginLeft: 'auto' },
  pluginDesc: { fontSize: '0.75rem', color: '#8a9aaa', marginBottom: 4 },
  pluginTools: { fontSize: '0.7rem', color: '#5a7a8a', marginBottom: 8 },
  pluginActions: { display: 'flex', gap: 6 },
  smallBtn: { padding: '3px 10px', borderRadius: 12, border: '1px solid rgba(255,255,255,0.15)', cursor: 'pointer', fontSize: '0.7rem', background: 'rgba(255,255,255,0.05)', color: '#c8d6e5' },
};

export default PluginManager;
