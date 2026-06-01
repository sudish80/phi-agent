import React, { useState } from 'react';
import TelemetryPanel from './TelemetryPanel';
import PluginManager from './PluginManager';
import AgentManager from './AgentManager';

const TABS = [
  { key: 'telemetry', label: 'Telemetry', icon: '📊' },
  { key: 'plugins', label: 'Plugins', icon: '🔌' },
  { key: 'agents', label: 'Agents', icon: '🤖' },
];

function Dashboard({ ws, onBack }) {
  const [activeTab, setActiveTab] = useState('telemetry');

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={onBack}>← Chat</button>
        <span style={styles.title}>Dashboard</span>
        <span style={styles.subtitle}>Server: localhost:8000</span>
      </div>

      <div style={styles.tabBar}>
        {TABS.map(t => (
          <button key={t.key} style={styles.tab(activeTab === t.key)} onClick={() => setActiveTab(t.key)}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div style={styles.content}>
        {activeTab === 'telemetry' && <TelemetryPanel ws={ws} />}
        {activeTab === 'plugins' && <PluginManager />}
        {activeTab === 'agents' && <AgentManager />}
      </div>
    </div>
  );
}

const C = { canvas: '#f7f7f4', ink: '#26251e', primary: '#f54e00', border: '#e6e5e0', font: "'Inter', system-ui, sans-serif", code: "'JetBrains Mono', monospace" };

const styles = {
  container: { display: 'flex', flexDirection: 'column', height: '100vh', background: C.canvas, color: C.ink, fontFamily: C.font },
  header: { display: 'flex', alignItems: 'center', gap: 16, padding: '12px 24px', background: '#fff', borderBottom: `1px solid ${C.border}` },
  backBtn: { padding: '6px 14px', borderRadius: 8, border: `1px solid ${C.border}`, cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, background: C.canvas, color: C.ink },
  title: { fontSize: '1.2rem', fontWeight: 700, color: C.ink, letterSpacing: '-0.02em' },
  subtitle: { fontSize: '0.7rem', color: '#888', marginLeft: 'auto', fontFamily: C.code },
  tabBar: { display: 'flex', gap: 0, padding: '0 16px', background: '#fff', borderBottom: `1px solid ${C.border}` },
  tab: (active) => ({
    padding: '10px 20px', border: 'none', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
    background: 'transparent', color: active ? C.primary : '#888',
    borderBottom: active ? `2px solid ${C.primary}` : '2px solid transparent',
    transition: 'all 0.2s',
  }),
  content: { flex: 1, overflow: 'hidden' },
};

export default Dashboard;
