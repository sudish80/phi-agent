/* Camera feed component - captures frames and sends to vision service. */

import React, { useRef, useEffect, useState, useCallback } from 'react';

function CameraFeed({ onCapture }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isActive, setIsActive] = useState(false);
  const [stream, setStream] = useState(null);
  const [capturedImage, setCapturedImage] = useState(null);

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  async function startCamera() {
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: 'user' },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = s;
      }
      setStream(s);
      setIsActive(true);
    } catch (e) {
      console.error('Camera error:', e);
      setIsActive(false);
    }
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      setStream(null);
    }
    setIsActive(false);
  }

  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    const base64Data = canvas.toDataURL('image/jpeg', 0.7).split(',')[1];
    setCapturedImage(base64Data);
    if (onCapture) onCapture(base64Data);
  }, [onCapture]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>Camera</div>
      <div style={styles.videoContainer}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={styles.video}
        />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        {!isActive && (
          <div style={styles.overlay}>
            Camera unavailable
          </div>
        )}
      </div>
      <div style={styles.controls}>
        <button style={styles.button(isActive)} onClick={captureFrame} disabled={!isActive}>
          Capture Frame
        </button>
      </div>
      {capturedImage && (
        <div style={styles.thumbnail}>
          <img
            src={`data:image/jpeg;base64,${capturedImage}`}
            alt="captured"
            style={{ width: '100%', borderRadius: 6 }}
          />
        </div>
      )}
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
  videoContainer: {
    position: 'relative',
    borderRadius: 8,
    overflow: 'hidden',
    background: '#000',
    aspectRatio: '4/3',
  },
  video: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transform: 'scaleX(-1)',
  },
  overlay: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(0,0,0,0.7)',
    color: '#666',
    fontSize: '0.8rem',
  },
  controls: {
    display: 'flex',
    gap: 8,
    marginTop: 8,
  },
  button: (active) => ({
    flex: 1,
    padding: '6px 12px',
    borderRadius: 8,
    border: 'none',
    background: active ? '#00d4ff' : '#2a4a5a',
    color: active ? '#0a0a1a' : '#6a8a9a',
    fontSize: '0.75rem',
    fontWeight: 600,
    cursor: active ? 'pointer' : 'not-allowed',
  }),
  thumbnail: {
    marginTop: 8,
    borderRadius: 8,
    overflow: 'hidden',
  },
};

export default CameraFeed;
