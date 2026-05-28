/* J.A.R.V.I.S. React Frontend
   WebSocket manager, audio capture, camera feed, Three.js avatar, equalizer.
*/

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Avatar from './Avatar';
import CameraFeed from './CameraFeed';
import AudioVisualizer from './AudioVisualizer';
import Controls from './Controls';
import Dashboard from './Dashboard';
import JarvisStartupAnimation from './JarvisStartupAnimation';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

function App() {
  const [sessionId] = useState(() => 'session_' + Date.now());
  const [ws, setWs] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [showStartup, setShowStartup] = useState(true);
  const [emotion, setEmotion] = useState('neutral');
  const [isSpeaking, setIsSpeaking] = useState(false);   // JARVIS is talking
  const [isListening, setIsListening] = useState(false);  // JARVIS is hearing you
  const [audioLevel, setAudioLevel] = useState(0);
  const [visemes, setVisemes] = useState([]);
  const [equalizerData, setEqualizerData] = useState(new Array(16).fill(0));
  const [micAvailable, setMicAvailable] = useState(true);
  const [showDashboard, setShowDashboard] = useState(false);

  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const reconnectTimeoutRef = useRef(null);
  const animFrameRef = useRef(null);
  const audioPlayerRef = useRef(null);

  /* ---- WebSocket connection ---- */
  const connectWs = useCallback(() => {
    const socket = new WebSocket(`${WS_URL}?session_id=${sessionId}`);

    socket.onopen = () => {
      setIsConnected(true);
      setShowStartup(false);
      console.log('WebSocket connected');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWsMessage(data);
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    socket.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected, reconnecting in 3s...');
      reconnectTimeoutRef.current = setTimeout(connectWs, 3000);
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      socket.close();
    };

    setWs(socket);
  }, [sessionId]);

  useEffect(() => {
    connectWs();
    const startupTimeout = setTimeout(() => setShowStartup(false), 6000);
    return () => {
      clearTimeout(startupTimeout);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (ws) ws.close();
    };
  }, [connectWs]);

  /* ---- WebSocket message handler ---- */
  function handleWsMessage(data) {
    const { type, payload } = data;

    switch (type) {
      case 'chat':
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: payload.reply, emotion: payload.emotion },
        ]);
        if (payload.emotion) setEmotion(payload.emotion);
        setIsSpeaking(true);
        setIsListening(false);
        if (payload.audio_url) {
          if (audioPlayerRef.current) { audioPlayerRef.current.pause(); audioPlayerRef.current = null; }
          const player = new Audio(payload.audio_url);
          player.play().catch(() => {});
          audioPlayerRef.current = player;
        }
        setTimeout(() => setIsSpeaking(false), 2000);
        break;

      case 'emotion':
        setEmotion(payload.emotion);
        break;

      case 'visemes':
        setVisemes(payload.frames || []);
        break;

      case 'audio_level':
        setAudioLevel(payload.level || 0);
        break;

      case 'listening':
        setIsListening(payload.active || false);
        if (payload.active) setIsSpeaking(false);
        break;

      case 'error':
        console.error('Server error:', payload.message);
        setMessages((prev) => [
          ...prev,
          { role: 'system', text: `Error: ${payload.message}` },
        ]);
        break;

      case 'pong':
        break;

      default:
        console.log('Unknown message type:', type);
    }
  }

  /* ---- Send chat message ---- */
  function sendMessage(text) {
    if (!text.trim() || !ws) return;

    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInputText('');

    ws.send(JSON.stringify({
      type: 'chat',
      payload: { text, emotion },
      session_id: sessionId,
    }));
  }

  /* ---- Audio capture & equalizer ---- */
  async function startAudioCapture() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 64;
      source.connect(analyserRef.current);

      function updateEqualizer() {
        if (!analyserRef.current) return;
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        setEqualizerData(Array.from(dataArray.slice(0, 16)));
        setAudioLevel(Math.max(...dataArray) / 255);
        animFrameRef.current = requestAnimationFrame(updateEqualizer);
      }
      updateEqualizer();

      mediaRecorderRef.current = new MediaRecorder(stream);
      mediaRecorderRef.current.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };
      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        audioChunksRef.current = [];
        if (ws && ws.readyState === WebSocket.OPEN) {
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64 = reader.result.split(',')[1];
            ws.send(JSON.stringify({
              type: 'audio',
              payload: { audio: base64 },
              session_id: sessionId,
            }));
          };
          reader.readAsDataURL(blob);
        }
      };
    } catch (e) {
      console.error('Audio capture error:', e);
      setMicAvailable(false);
    }
  }

  useEffect(() => {
    startAudioCapture();
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
      if (audioPlayerRef.current) audioPlayerRef.current.pause();
    };
  }, []);

  /* ---- Send image to server ---- */
  function handleImageCapture(imageBase64) {
    if (!ws) return;
    ws.send(JSON.stringify({
      type: 'image',
      payload: { image: imageBase64 },
      session_id: sessionId,
    }));
  }

  if (showStartup) return <JarvisStartupAnimation />;

  if (showDashboard) {
    return <Dashboard ws={ws} onBack={() => setShowDashboard(false)} />;
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.logo}>
          <span style={{ color: '#00d4ff', fontWeight: 700 }}>J.A.R.V.I.S.</span>
          <span style={styles.statusDot(isConnected)} />
        </div>
        {!micAvailable && (
          <a href="/chat.html" style={styles.micFallbackLink}>
            No mic detected — use text chat
          </a>
        )}
        <button style={styles.dashBtn} onClick={() => setShowDashboard(true)}>Dashboard</button>
        <div style={styles.sessionInfo}>
          Session: {sessionId.slice(0, 12)}...
        </div>
      </div>

      {/* Main layout */}
      <div style={styles.main}>
        {/* Left: Avatar */}
        <div style={styles.avatarPanel}>
          <Avatar
            emotion={emotion}
            isSpeaking={isSpeaking}
            isListening={isListening}
            visemes={visemes}
            equalizerData={equalizerData}
          />
        </div>

        {/* Center: Chat */}
        <div style={styles.chatPanel}>
          <div style={styles.messagesContainer}>
            {messages.map((msg, i) => (
              <div key={i} style={styles.messageBubble(msg.role)}>
                <div style={styles.messageRole}>
                  {msg.role === 'user' ? 'You' : 'J.A.R.V.I.S.'}
                </div>
                <div style={styles.messageText}>{msg.text}</div>
              </div>
            ))}
          </div>

          {/* Input */}
          <div style={styles.inputArea}>
            <input
              style={styles.input}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage(inputText)}
              placeholder="Talk to J.A.R.V.I.S...."
              disabled={!isConnected}
            />
            <button
              style={styles.sendButton(isConnected)}
              onClick={() => sendMessage(inputText)}
              disabled={!isConnected}
            >
              Send
            </button>
          </div>
        </div>

        {/* Right: Camera + Audio Visualizer + Controls */}
        <div style={styles.sidePanel}>
          <CameraFeed onCapture={handleImageCapture} />
          <AudioVisualizer
            audioLevel={audioLevel}
            equalizerData={equalizerData}
            isSpeaking={isSpeaking}
            isListening={isListening}
          />
          <Controls
            isConnected={isConnected}
            emotion={emotion}
            ws={ws}
            sessionId={sessionId}
          />
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: 'linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0a0a1a 100%)',
    color: '#c8d6e5',
    fontFamily: "'Segoe UI', system-ui, sans-serif",
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 24px',
    background: 'rgba(0, 20, 40, 0.8)',
    borderBottom: '1px solid rgba(0, 212, 255, 0.2)',
    backdropFilter: 'blur(10px)',
    zIndex: 10,
  },
  logo: { fontSize: '1.4rem', display: 'flex', alignItems: 'center', gap: 10 },
  statusDot: (connected) => ({
    display: 'inline-block',
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: connected ? '#00ff88' : '#ff4444',
    boxShadow: connected
      ? '0 0 8px #00ff88'
      : '0 0 8px #ff4444',
    transition: 'all 0.3s',
  }),
  dashBtn: { padding: '6px 14px', borderRadius: 16, border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, background: 'rgba(0,212,255,0.15)', color: '#00d4ff', marginLeft: 'auto', marginRight: 12 },
  sessionInfo: { fontSize: '0.75rem', color: '#5a7a8a', fontFamily: 'monospace' },
  micFallbackLink: {
    fontSize: '0.75rem',
    color: '#f59e0b',
    textDecoration: 'underline',
    cursor: 'pointer',
    marginRight: 'auto',
    marginLeft: 12,
  },
  main: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  avatarPanel: {
    flex: 2,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    borderRight: '1px solid rgba(0, 212, 255, 0.1)',
    minWidth: 300,
  },
  chatPanel: {
    flex: 3,
    display: 'flex',
    flexDirection: 'column',
    borderRight: '1px solid rgba(0, 212, 255, 0.1)',
  },
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  messageBubble: (role) => ({
    alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
    background: role === 'user'
      ? 'rgba(0, 212, 255, 0.15)'
      : 'rgba(255, 255, 255, 0.05)',
    borderRadius: role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
    padding: '12px 16px',
    maxWidth: '80%',
    border: `1px solid ${role === 'user' ? 'rgba(0, 212, 255, 0.3)' : 'rgba(255,255,255,0.1)'}`,
  }),
  messageRole: { fontSize: '0.7rem', fontWeight: 600, color: '#00d4ff', marginBottom: 4 },
  messageText: { fontSize: '0.9rem', lineHeight: 1.4 },
  inputArea: {
    display: 'flex',
    gap: 8,
    padding: 16,
    borderTop: '1px solid rgba(0, 212, 255, 0.2)',
    background: 'rgba(0, 0, 0, 0.3)',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    borderRadius: 24,
    border: '1px solid rgba(0, 212, 255, 0.3)',
    background: 'rgba(255,255,255,0.05)',
    color: '#fff',
    fontSize: '0.95rem',
    outline: 'none',
    fontFamily: 'inherit',
  },
  sendButton: (enabled) => ({
    padding: '12px 24px',
    borderRadius: 24,
    border: 'none',
    background: enabled ? '#00d4ff' : '#2a4a5a',
    color: enabled ? '#0a0a1a' : '#6a8a9a',
    fontWeight: 600,
    cursor: enabled ? 'pointer' : 'not-allowed',
    transition: 'all 0.2s',
  }),
  sidePanel: {
    flex: 1.5,
    display: 'flex',
    flexDirection: 'column',
    padding: 12,
    gap: 12,
    minWidth: 220,
    overflowY: 'auto',
  },
};

export default App;
