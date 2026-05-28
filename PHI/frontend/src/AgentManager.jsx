import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://localhost:8000';

const ROLES = ['researcher', 'coder', 'reviewer', 'writer', 'analyst'];

function AgentManager() {
  const [agents, setAgents] = useState([]);
  const [selectedRole, setSelectedRole] = useState('researcher');
  const [taskInput, setTaskInput] = useState('');
  const [collabTask, setCollabTask] = useState('');
  const [collabRoles, setCollabRoles] = useState(['researcher', 'coder']);
  const [message, setMessage] = useState('');

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API}/agents`);
      const data = await res.json();
      setAgents(data.agents || data);
    } catch (e) {
      console.error('Failed to fetch agents:', e);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, 3000);
    return () => clearInterval(interval);
  }, [fetchAgents]);

  const apiCall = async (endpoint, body) => {
    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setMessage(data.message || data.status || JSON.stringify(data).slice(0, 120));
      setTimeout(() => setMessage(''), 4000);
      fetchAgents();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    }
  };

  const spawnAgent = () => {
    if (!taskInput.trim()) return;
    apiCall('/agents/spawn', { role: selectedRole, task: taskInput });
    setTaskInput('');
  };

  const cancelAgent = (id) => apiCall(`/agents/${id}/cancel`);

  const startCollaboration = () => {
    if (!collabTask.trim() || collabRoles.length === 0) return;
    apiCall('/agents/collaborate', { task: collabTask, roles: collabRoles });
    setCollabTask('');
  };

  const toggleCollabRole = (role) => {
    setCollabRoles(prev =>
      prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]
    );
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Multi-Agent Orchestrator</h2>

      {message && <div style={styles.message}>{message}</div>}

      {/* Spawn single agent */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Spawn Agent</h3>
        <div style={styles.row}>
          <select style={styles.select} value={selectedRole} onChange={e => setSelectedRole(e.target.value)}>
            {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
          <input style={styles.input} value={taskInput} onChange={e => setTaskInput(e.target.value)}
            placeholder="Task description..." onKeyDown={e => e.key === 'Enter' && spawnAgent()} />
          <button style={styles.btn} onClick={spawnAgent}>Spawn</button>
        </div>
      </div>

      {/* Collaborate */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Collaborate</h3>
        <div style={styles.row}>
          <input style={{ ...styles.input, flex: 2 }} value={collabTask} onChange={e => setCollabTask(e.target.value)}
            placeholder="Task for collaboration..." onKeyDown={e => e.key === 'Enter' && startCollaboration()} />
          <button style={styles.btn} onClick={startCollaboration}>Go</button>
        </div>
        <div style={styles.rolePicker}>
          {ROLES.map(r => (
            <label key={r} style={styles.checkLabel}>
              <input type="checkbox" checked={collabRoles.includes(r)} onChange={() => toggleCollabRole(r)} />
              {r}
            </label>
          ))}
        </div>
      </div>

      {/* Agent list */}
      <div style={styles.agentList}>
        {agents.length === 0 && <div style={styles.empty}>No active agents</div>}
        {agents.map((a, i) => (
          <div key={a.id || i} style={styles.agentCard}>
            <div style={styles.agentHeader}>
              <span style={styles.agentRole}>{a.role || '?'}</span>
              <span style={{ ...styles.badge, background: a.status === 'running' ? 'rgba(0,212,255,0.2)' : a.status === 'completed' ? 'rgba(0,255,136,0.2)' : a.status === 'error' ? 'rgba(255,68,68,0.2)' : 'rgba(255,255,255,0.1)', color: a.status === 'running' ? '#00d4ff' : a.status === 'completed' ? '#00ff88' : a.status === 'error' ? '#ff4444' : '#8a9aaa' }}>
                {a.status || 'unknown'}
              </span>
              <span style={styles.agentId}>{a.id?.slice(0, 12) || ''}</span>
              {a.status === 'running' && (
                <button style={styles.cancelBtn} onClick={() => cancelAgent(a.id)}>Cancel</button>
              )}
            </div>
            <div style={styles.agentTask}>{a.task?.slice(0, 150)}</div>
            {a.result && (
              <details style={styles.agentResult}>
                <summary style={styles.resultSummary}>Result</summary>
                <pre style={styles.resultPre}>{typeof a.result === 'string' ? a.result : JSON.stringify(a.result, null, 2)}</pre>
              </details>
            )}
            {a.error && <div style={styles.agentError}>{a.error.slice(0, 200)}</div>}
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
  section: { marginBottom: 16 },
  sectionTitle: { color: '#8a9aaa', fontSize: '0.85rem', fontWeight: 600, margin: '0 0 8px 0' },
  row: { display: 'flex', gap: 8 },
  select: { padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)', color: '#c8d6e5', fontSize: '0.8rem', outline: 'none' },
  input: { flex: 1, padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)', color: '#fff', fontSize: '0.8rem', outline: 'none' },
  btn: { padding: '8px 18px', borderRadius: 16, border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, background: '#00d4ff', color: '#0a0a1a', whiteSpace: 'nowrap' },
  rolePicker: { display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' },
  checkLabel: { display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', color: '#8a9aaa', cursor: 'pointer' },
  empty: { color: '#5a7a8a', textAlign: 'center', padding: 40 },
  agentList: { display: 'flex', flexDirection: 'column', gap: 8, overflow: 'auto', flex: 1 },
  agentCard: { background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 12, border: '1px solid rgba(255,255,255,0.06)' },
  agentHeader: { display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 },
  agentRole: { fontWeight: 600, color: '#c8d6e5', fontSize: '0.85rem' },
  badge: { padding: '1px 8px', borderRadius: 10, fontSize: '0.65rem', fontWeight: 700 },
  agentId: { fontSize: '0.7rem', color: '#5a7a8a', marginLeft: 'auto' },
  cancelBtn: { padding: '2px 8px', borderRadius: 8, border: '1px solid rgba(255,68,68,0.3)', cursor: 'pointer', fontSize: '0.65rem', background: 'rgba(255,68,68,0.1)', color: '#ff4444' },
  agentTask: { fontSize: '0.75rem', color: '#8a9aaa', marginBottom: 4 },
  agentResult: { marginTop: 4 },
  resultSummary: { fontSize: '0.7rem', color: '#00d4ff', cursor: 'pointer' },
  resultPre: { fontSize: '0.7rem', color: '#c8d6e5', background: 'rgba(0,0,0,0.3)', padding: 8, borderRadius: 4, maxHeight: 150, overflow: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace' },
  agentError: { fontSize: '0.7rem', color: '#ff4444', marginTop: 4 },
};

export default AgentManager;
