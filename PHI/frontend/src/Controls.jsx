/* Control panel for J.A.R.V.I.S. - emotion override, settings, commands. */

import React, { useState } from 'react';

const EMOTIONS = [
  'neutral', 'happy', 'serious', 'excited', 'calm', 'angry', 'sad', 'whisper',
];

function Controls({ isConnected, emotion, ws, sessionId }) {
  const [selectedEmotion, setSelectedEmotion] = useState(emotion);

  function sendCommand(command) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
      type: 'command',
      payload: { command },
      session_id: sessionId,
    }));
  }

  function setEmotionOverride(e) {
    const newEmotion = e.target.value;
    setSelectedEmotion(newEmotion);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'command',
        payload: { command: 'set_emotion', emotion: newEmotion },
        session_id: sessionId,
      }));
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>Controls</div>

      {/* Connection status */}
      <div style={styles.statusRow}>
        <div
          style={{
            ...styles.statusDot,
            background: isConnected ? '#00ff88' : '#ff4444',
            boxShadow: isConnected ? '0 0 6px #00ff88' : '0 0 6px #ff4444',
          }}
        />
        <span style={styles.statusText}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Current emotion */}
      <div style={styles.section}>
        <div style={styles.label}>Current Emotion</div>
        <div style={styles.emotionDisplay}>
          {emotion.toUpperCase()}
        </div>
      </div>

      {/* Emotion override */}
      <div style={styles.section}>
        <div style={styles.label}>Override Emotion</div>
        <select
          style={styles.select}
          value={selectedEmotion}
          onChange={setEmotionOverride}
        >
          {EMOTIONS.map((e) => (
            <option key={e} value={e}>
              {e.charAt(0).toUpperCase() + e.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Quick commands */}
      <div style={styles.section}>
        <div style={styles.label}>Quick Commands</div>
        <div style={styles.buttonGrid}>
          <button
            style={styles.quickBtn}
            onClick={() => sendCommand('reset_session')}
          >
            Reset Session
          </button>
          <button
            style={styles.quickBtn}
            onClick={() => sendCommand('get_status')}
          >
            Get Status
          </button>
        </div>
      </div>

      {/* Info */}
      <div style={styles.infoText}>
        Session: {sessionId.slice(0, 8)}...
      </div>
    </div>
  );
}

const styles = {
  container: {
    background: 'rgba(0, 20, 40, 0.5)',
    borderRadius: 12,
    padding: 12,
    border: '1px solid rgba(0, 212, 255, 0.15)',
    fontSize: '0.8rem',
  },
  header: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#00d4ff',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 10,
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    transition: 'all 0.3s',
  },
  statusText: {
    color: '#8a9aaa',
    fontSize: '0.75rem',
  },
  section: {
    marginBottom: 12,
  },
  label: {
    fontSize: '0.65rem',
    color: '#5a7a8a',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  emotionDisplay: {
    fontSize: '1.1rem',
    fontWeight: 700,
    color: '#00d4ff',
    letterSpacing: 2,
    textShadow: '0 0 10px rgba(0,212,255,0.3)',
  },
  select: {
    width: '100%',
    padding: '6px 8px',
    borderRadius: 6,
    border: '1px solid rgba(0, 212, 255, 0.3)',
    background: 'rgba(255,255,255,0.05)',
    color: '#c8d6e5',
    fontSize: '0.8rem',
    outline: 'none',
    cursor: 'pointer',
  },
  buttonGrid: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap',
  },
  quickBtn: {
    padding: '6px 12px',
    borderRadius: 8,
    border: '1px solid rgba(0, 212, 255, 0.3)',
    background: 'rgba(0, 212, 255, 0.1)',
    color: '#00d4ff',
    fontSize: '0.7rem',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  infoText: {
    fontSize: '0.6rem',
    color: '#4a6a7a',
    fontFamily: 'monospace',
    marginTop: 8,
  },
};

export default Controls;
