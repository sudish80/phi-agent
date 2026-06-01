import React from 'react';

export default function PhiStartupAnimation() {
  return (
    <div className="relative flex items-center justify-center w-screen h-screen overflow-hidden bg-black text-cyan-400 font-mono">
      {/* Background Grid */}
      <div className="absolute inset-0 opacity-20">
        <div
          className="w-full h-full"
          style={{
            backgroundImage:
              'linear-gradient(rgba(0,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,255,0.15) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
      </div>

      {/* Rotating Rings */}
      <div className="absolute flex items-center justify-center">
        <div className="absolute w-[420px] h-[420px] border border-cyan-400 rounded-full animate-spin opacity-40" />
        <div className="absolute w-[320px] h-[320px] border-2 border-cyan-300 rounded-full animate-pulse" />
        <div className="absolute w-[220px] h-[220px] border border-cyan-500 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '8s' }} />
      </div>

      {/* Core */}
      <div className="relative flex flex-col items-center justify-center z-10">
        <div className="w-28 h-28 rounded-full border-4 border-cyan-400 shadow-[0_0_40px_rgba(0,255,255,0.8)] animate-pulse flex items-center justify-center">
          <div className="w-10 h-10 bg-cyan-400 rounded-full shadow-[0_0_20px_rgba(0,255,255,1)]" />
        </div>

        {/* Title */}
        <h1 className="mt-10 text-5xl tracking-[0.4em] text-cyan-300 animate-pulse">
          PHI
        </h1>

        {/* Boot Sequence */}
        <div className="mt-8 w-[400px] text-sm text-cyan-200 space-y-2">
          <p className="animate-pulse">Initializing AI Core...</p>
          <p className="animate-pulse delay-150">Loading Neural Systems...</p>
          <p className="animate-pulse delay-300">Connecting Voice Interface...</p>
          <p className="animate-pulse delay-500">System Online.</p>
        </div>

        {/* Progress Bar */}
        <div className="mt-6 w-[400px] h-3 border border-cyan-400 rounded-full overflow-hidden">
          <div className="h-full bg-cyan-400 animate-[loading_4s_linear_forwards] shadow-[0_0_20px_rgba(0,255,255,1)]" />
        </div>
      </div>

      {/* Floating Particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {Array.from({ length: 60 }).map((_, i) => (
          <div
            key={i}
            className="absolute bg-cyan-300 rounded-full opacity-70 animate-ping"
            style={{
              width: `${Math.random() * 4 + 2}px`,
              height: `${Math.random() * 4 + 2}px`,
              top: `${Math.random() * 100}%`,
              left: `${Math.random() * 100}%`,
              animationDuration: `${Math.random() * 5 + 2}s`,
            }}
          />
        ))}
      </div>

      <style>{`
        @keyframes loading {
          from { width: 0%; }
          to { width: 100%; }
        }
      `}</style>
    </div>
  );
}
