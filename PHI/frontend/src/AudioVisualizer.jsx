/* Audio visualizer with equalizer bars that animate in real-time. */

import React, { useMemo } from 'react';

function EqualizerBars({ data, isActive, color }) {
  const bars = useMemo(() => {
    if (!data || data.length === 0) return Array(16).fill(0);
    return data;
  }, [data]);

  return (
    <div style={styles.barContainer}>
      {bars.map((level, i) => {
        const height = isActive ? Math.max(4, (level / 255) * 80) : 4;
        return (
          <div
            key={i}
            style={{
              ...styles.bar,
              height: `${height}px`,
              background: isActive ? `linear-gradient(to top, ${color}, ${color}88)` : '#1a2a3a',
              boxShadow: isActive ? `0 0 ${4 + (level / 255) * 8}px ${color}66` : 'none',
              transition: 'height 0.05s ease',
            }}
          />
        );
      })}
    </div>
  );
}

function AudioVisualizer({ audioLevel = 0, equalizerData = [], isSpeaking = false, isListening = false }) {
  const levelPercent = Math.min(100, audioLevel * 100);
  const isActive = isSpeaking || isListening;
  const color = isSpeaking ? '#00ff88' : (isListening ? '#ff8800' : '#00d4ff');
  const modeLabel = isSpeaking ? 'TALKING' : (isListening ? 'LISTENING' : 'IDLE');

  return (
    <div style={styles.container}>
      <div style={styles.header}>Audio</div>

      {/* Volume level */}
      <div style={styles.levelContainer}>
        <div style={styles.levelTrack}>
          <div
            style={{
              ...styles.levelFill,
              width: `${levelPercent}%`,
              background: isActive
                ? `linear-gradient(90deg, ${color}, ${color}dd)`
                : `linear-gradient(90deg, #00d4ff, #004466)`,
              boxShadow: isActive ? `0 0 10px ${color}` : 'none',
              transition: 'width 0.05s ease',
            }}
          />
        </div>
        <div style={{ ...styles.levelLabel, color: isActive ? color : '#5a7a8a' }}>
          {modeLabel}
        </div>
      </div>

      {/* Equalizer bars */}
      <div style={styles.equalizerContainer}>
        <EqualizerBars
          data={equalizerData}
          isActive={isActive}
          color={color}
        />
      </div>

      {/* Audio waveform dots */}
      <div style={styles.waveform}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            style={{
              ...styles.waveDot,
              animationDelay: `${i * 0.1}s`,
              opacity: isActive ? 0.6 + (audioLevel * 0.4) : 0.2,
              background: color,
            }}
          />
        ))}
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
  },
  header: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#00d4ff',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 8,
  },
  levelContainer: {
    marginBottom: 8,
  },
  levelTrack: {
    height: 6,
    background: 'rgba(255,255,255,0.1)',
    borderRadius: 3,
    overflow: 'hidden',
  },
  levelFill: {
    height: '100%',
    borderRadius: 3,
    transition: 'width 0.1s ease',
  },
  levelLabel: {
    fontSize: '0.6rem',
    color: '#5a7a8a',
    marginTop: 4,
    textAlign: 'right',
    letterSpacing: 1,
  },
  equalizerContainer: {
    marginBottom: 8,
  },
  barContainer: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 2,
    height: 84,
    justifyContent: 'center',
  },
  bar: {
    width: 6,
    borderRadius: '3px 3px 0 0',
    minHeight: 2,
  },
  waveform: {
    display: 'flex',
    justifyContent: 'center',
    gap: 6,
  },
  waveDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    animation: 'pulse 0.8s infinite alternate',
  },
};

/* Inject keyframes for dot animation */
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes pulse {
    from { transform: scale(0.8); }
    to { transform: scale(1.4); }
  }
`;
document.head.appendChild(styleSheet);

export default AudioVisualizer;
