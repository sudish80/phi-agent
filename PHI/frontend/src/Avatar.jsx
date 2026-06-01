/* 2D Audio Equalizer — replaces the 3D Three.js avatar.
   Renders animated frequency bars, waveform, and emotion status.
   Pure CSS + Canvas — no Three.js dependency.
*/

import React, { useRef, useEffect, useMemo } from 'react';

const BAR_COUNT = 24;
const EMOTION_COLORS = {
  neutral:  { primary: '#00d4ff', secondary: '#004466', accent: '#0077aa' },
  happy:    { primary: '#00ff88', secondary: '#006633', accent: '#00cc66' },
  serious:  { primary: '#4488ff', secondary: '#003366', accent: '#2266cc' },
  excited:  { primary: '#ff6600', secondary: '#663300', accent: '#cc5500' },
  calm:     { primary: '#88ddff', secondary: '#224466', accent: '#5599bb' },
  angry:    { primary: '#ff2244', secondary: '#660011', accent: '#cc1133' },
  sad:      { primary: '#6688cc', secondary: '#223366', accent: '#4466aa' },
  whisper:  { primary: '#aabbdd', secondary: '#334466', accent: '#7788aa' },
};

function EqualizerBars({ data, isActive, color, barCount }) {
  const canvasRef = useRef();
  const animRef = useRef();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;

    function draw() {
      ctx.clearRect(0, 0, w, h);
      const count = barCount || data.length || 16;
      const gap = 2;
      const barW = (w - gap * (count - 1)) / count;
      const cx = w / 2;
      const cy = h / 2;

      for (let i = 0; i < count; i++) {
        const val = data[i] || 0;
        const pct = val / 255;
        const barH = isActive ? Math.max(2, pct * h * 0.7) : 2;
        const x = i * (barW + gap);
        const y = cy - barH / 2;

        const grad = ctx.createLinearGradient(x, y, x, y + barH);
        const c = isActive ? color : '#1a2a3a';
        grad.addColorStop(0, c);
        grad.addColorStop(1, c + '44');
        ctx.fillStyle = grad;

        ctx.beginPath();
        const r = barW / 2;
        ctx.roundRect(x, y, barW, barH, r);
        ctx.fill();

        if (isActive && val > 0) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 4 + pct * 8;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      }

      if (isActive) animRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [data, isActive, color, barCount]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}

function WaveCircle({ isActive, color, mode }) {
  const canvasRef = useRef();
  const animRef = useRef();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !isActive) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;
    const cx = w / 2;
    const cy = h / 2;
    let phase = 0;

    function draw() {
      ctx.clearRect(0, 0, w, h);
      phase += 0.04;

      for (let ring = 0; ring < 3; ring++) {
        const baseR = 20 + ring * 14 + Math.sin(phase + ring * 1.2) * 6;
        ctx.beginPath();
        ctx.arc(cx, cy, baseR, 0, Math.PI * 2);
        ctx.strokeStyle = color + Math.floor(60 + Math.sin(phase * 0.5 + ring) * 30).toString(16).padStart(2, '0');
        ctx.lineWidth = 1.5 - ring * 0.3;
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [isActive, color, mode]);

  if (!isActive) return null;

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: '160px', height: '160px',
        pointerEvents: 'none',
      }}
    />
  );
}

function VisualizerRing({ currentColor, isActive, barCount }) {
  const ringRef = useRef();
  const animRef = useRef();

  useEffect(() => {
    const canvas = ringRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;
    const cx = w / 2;
    const cy = h / 2;
    const r = Math.min(w, h) * 0.32;
    let phase = 0;

    function draw() {
      ctx.clearRect(0, 0, w, h);
      phase += 0.03;
      const count = barCount || 24;

      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
        const wave = isActive ? Math.sin(phase + i * 0.5) * 0.3 + 0.7 : 0.2;
        const len = 8 + wave * 20;

        const x1 = cx + Math.cos(angle) * r;
        const y1 = cy + Math.sin(angle) * r;
        const x2 = cx + Math.cos(angle) * (r + len);
        const y2 = cy + Math.sin(angle) * (r + len);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = isActive
          ? `hsl(${200 + wave * 40}, 80%, ${40 + wave * 30}%)`
          : '#1a3a4a';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [currentColor, isActive, barCount]);

  return (
    <canvas
      ref={ringRef}
      style={{
        position: 'absolute', top: 0, left: 0,
        width: '100%', height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
}

function Avatar({ emotion = 'neutral', isSpeaking = false, isListening = false, visemes = [], equalizerData = [] }) {
  const colors = EMOTION_COLORS[emotion] || EMOTION_COLORS.neutral;
  const isActive = isSpeaking || isListening;
  const modeColor = isSpeaking ? colors.primary : (isListening ? '#ff8800' : '#555');
  const modeLabel = isSpeaking ? 'TALKING' : (isListening ? 'LISTENING' : 'IDLE');
  const freqData = useMemo(() => {
    if (!equalizerData || equalizerData.length === 0) return new Array(BAR_COUNT).fill(0);
    if (equalizerData.length >= BAR_COUNT) return equalizerData.slice(0, BAR_COUNT);
    const padded = [...equalizerData];
    while (padded.length < BAR_COUNT) padded.push(0);
    return padded;
  }, [equalizerData]);

  return (
    <div style={{
      width: '100%',
      height: '100%',
      minHeight: 400,
      background: `radial-gradient(ellipse at center 40%, ${colors.secondary}22 0%, #0a0a1a 70%)`,
      borderRadius: 16,
      overflow: 'hidden',
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      {/* Top section: equalizer bars + circular visualizer */}
      <div style={{
        position: 'relative',
        width: '80%',
        maxWidth: 500,
        height: '55%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <VisualizerRing
          currentColor={colors.primary}
          isActive={isActive}
          barCount={BAR_COUNT}
        />
        <WaveCircle isActive={isActive} color={colors.primary} mode={modeLabel} />
      </div>

      {/* Frequency bar equalizer */}
      <div style={{
        width: '85%',
        maxWidth: 480,
        height: 80,
        marginTop: -10,
      }}>
        <EqualizerBars
          data={freqData}
          isActive={isActive}
          color={modeColor}
          barCount={BAR_COUNT}
        />
      </div>

      {/* Emotion + mode status */}
      <div style={{
        display: 'flex',
        gap: 12,
        marginTop: 16,
        alignItems: 'center',
      }}>
        <div style={{
          padding: '4px 14px',
          borderRadius: 12,
          fontSize: '0.7rem',
          fontWeight: 700,
          color: modeColor,
          border: `1px solid ${modeColor}44`,
          background: `${modeColor}11`,
          textTransform: 'uppercase',
          letterSpacing: 1.5,
          transition: 'all 0.3s',
        }}>
          {modeLabel}
        </div>
        <div style={{
          padding: '4px 14px',
          borderRadius: 12,
          fontSize: '0.7rem',
          color: colors.primary,
          border: `1px solid ${colors.primary}33`,
          background: `${colors.primary}11`,
          textTransform: 'uppercase',
          letterSpacing: 1.5,
        }}>
          {emotion}
        </div>
      </div>

      {/* Signal bar indicator */}
      <div style={{
        display: 'flex',
        gap: 3,
        marginTop: 12,
        alignItems: 'center',
      }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{
            width: 20,
            height: 3,
            borderRadius: 2,
            background: isActive ? modeColor : '#1a2a3a',
            opacity: isActive ? 0.3 + (i / 5) * 0.7 : 0.3,
            transition: 'all 0.2s',
          }} />
        ))}
      </div>
    </div>
  );
}

export default Avatar;
