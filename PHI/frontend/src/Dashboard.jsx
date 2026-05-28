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

const styles = {
  container: { display: 'flex', flexDirection: 'column', height: '100vh', background: 'linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0a0a1a 100%)', color: '#c8d6e5', fontFamily: "'Segoe UI', system-ui, sans-serif" },
  header: { display: 'flex', alignItems: 'center', gap: 16, padding: '12px 24px', background: 'rgba(0, 20, 40, 0.8)', borderBottom: '1px solid rgba(0, 212, 255, 0.2)', backdropFilter: 'blur(10px)' },
  backBtn: { padding: '6px 14px', borderRadius: 16, border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, background: 'rgba(255,255,255,0.1)', color: '#c8d6e5' },
  title: { fontSize: '1.2rem', fontWeight: 700, color: '#00d4ff' },
  subtitle: { fontSize: '0.75rem', color: '#5a7a8a', marginLeft: 'auto', fontFamily: 'monospace' },
  tabBar: { display: 'flex', gap: 0, padding: '0 16px', background: 'rgba(0,0,0,0.2)', borderBottom: '1px solid rgba(255,255,255,0.05)' },
  tab: (active) => ({
    padding: '10px 20px', border: 'none', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
    background: 'transparent', color: active ? '#00d4ff' : '#6a8a9a',
    borderBottom: active ? '2px solid #00d4ff' : '2px solid transparent',
    transition: 'all 0.2s',
  }),
  content: { flex: 1, overflow: 'hidden' },
};

export default Dashboard;
