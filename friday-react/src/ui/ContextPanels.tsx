import { useAIStore } from '../core/store';
import { motion, AnimatePresence } from 'framer-motion';
import { Cloud, Terminal, AlertTriangle, Command, Clock } from 'lucide-react';
import { useState, useEffect } from 'react';

const PANEL_ICONS = {
  weather: Cloud,
  code: Terminal,
  alert: AlertTriangle,
  command: Command,
};

const STATE_COLORS = {
  idle: { primary: '#00d4ff', secondary: '#613187', glow: 'rgba(0, 212, 255, 0.4)' },
  listening: { primary: '#00ffff', secondary: '#8000ff', glow: 'rgba(0, 255, 255, 0.4)' },
  thinking: { primary: '#3366ff', secondary: '#ff13cc', glow: 'rgba(51, 102, 255, 0.4)' },
  responding: { primary: '#22ffcc', secondary: '#00ff80', glow: 'rgba(34, 255, 204, 0.4)' },
  error: { primary: '#ff2244', secondary: '#ff8000', glow: 'rgba(255, 34, 68, 0.4)' },
};

// Glitch effect for panel text
function GlitchText({ children, active }: { children: string; active: boolean }) {
  const [glitched, setGlitched] = useState('');

  useEffect(() => {
    if (!active) { setGlitched(''); return; }
    const chars = '!<>-_\\/[]{}—=+*^?#@$&%';
    let interval: ReturnType<typeof setInterval>;
    let timeout: ReturnType<typeof setTimeout>;

    const start = () => {
      let i = 0;
      interval = setInterval(() => {
        const randomChars = children
          .split('')
          .map((c, j) => {
            if (j < i) return c;
            return chars[Math.floor(Math.random() * chars.length)];
          })
          .join('');
        setGlitched(randomChars);
        i = Math.min(i + 2, children.length);
        if (i >= children.length) {
          clearInterval(interval);
          timeout = setTimeout(() => { setGlitched(''); }, 800);
        }
      }, 30);
    };

    start();
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [children, active]);

  return <>{glitched || children}</>;
}

export function ContextPanels() {
  const panels = useAIStore((s) => s.panels);
  const state = useAIStore((s) => s.state);
  const colors = STATE_COLORS[state] || STATE_COLORS.idle;

  return (
    <div className="absolute right-8 top-1/2 -translate-y-1/2 flex flex-col gap-5 z-20 perspective-[1200px] pointer-events-none">
      <AnimatePresence mode="popLayout">
        {panels.map((panel, idx) => {
          const Icon = PANEL_ICONS[panel.type as keyof typeof PANEL_ICONS] || Command;
          const isAlert = panel.type === 'alert';
          const delay = idx * 0.08;

          return (
            <motion.div
              key={panel.id}
              layout
              initial={{ opacity: 0, x: 80, rotateY: -20, scale: 0.85, filter: 'blur(10px)' }}
              animate={{
                opacity: 1 - idx * 0.18,
                x: 0,
                rotateY: 0,
                scale: 1 - idx * 0.04,
                filter: `blur(${idx * 0.5}px)`,
              }}
              exit={{ opacity: 0, x: 100, scale: 0.9, filter: 'blur(15px)' }}
              transition={{
                type: 'spring',
                stiffness: 220,
                damping: 24,
                delay,
              }}
              className="relative w-80 rounded-xl overflow-hidden pointer-events-auto"
              style={{
                background: `linear-gradient(135deg, rgba(0,0,0,0.85) 0%, rgba(${isAlert ? '40,0,0' : '0,20,40'},0.8) 100%)`,
                backdropFilter: 'blur(16px)',
                border: `1px solid ${isAlert ? '#ff2244' : colors.primary}30`,
                boxShadow: `
                  0 0 30px ${isAlert ? 'rgba(255,34,68,0.15)' : colors.glow}30,
                  inset 0 0 40px ${isAlert ? 'rgba(255,34,68,0.05)' : colors.glow}10,
                  0 20px 60px rgba(0,0,0,0.5)
                `,
              }}
            >
              {/* Animated scan line */}
              <motion.div
                animate={{ top: ['-5%', '105%'] }}
                transition={{ repeat: Infinity, duration: 2.5, ease: 'linear', delay: idx * 0.4 }}
                className="absolute left-0 right-0 h-0.5 z-10 pointer-events-none"
                style={{
                  background: `linear-gradient(90deg, transparent, ${isAlert ? '#ff2244' : colors.primary}80, transparent)`,
                  boxShadow: `0 0 12px ${isAlert ? '#ff2244' : colors.primary}`,
                }}
              />

              {/* Top accent line */}
              <div
                className="absolute top-0 left-0 right-0 h-px"
                style={{
                  background: `linear-gradient(90deg, transparent, ${isAlert ? '#ff2244' : colors.primary}, transparent)`,
                  boxShadow: `0 0 8px ${isAlert ? '#ff2244' : colors.primary}`,
                }}
              />

              {/* Corner accents */}
              {[
                { top: 0, left: 0, rotate: '0deg' },
                { top: 0, right: 0, rotate: '90deg' },
                { bottom: 0, right: 0, rotate: '180deg' },
                { bottom: 0, left: 0, rotate: '270deg' },
              ].map((pos, ci) => (
                <div
                  key={ci}
                  className="absolute w-4 h-4"
                  style={{
                    ...pos,
                    borderTop: `1px solid ${isAlert ? '#ff2244' : colors.primary}60`,
                    borderLeft: ci < 2 ? `1px solid ${isAlert ? '#ff2244' : colors.primary}60` : 'none',
                    borderRight: ci >= 2 ? `1px solid ${isAlert ? '#ff2244' : colors.primary}60` : 'none',
                    borderBottom: ci >= 1 && ci < 3 ? `1px solid ${isAlert ? '#ff2244' : colors.primary}60` : 'none',
                  }}
                />
              ))}

              {/* Header */}
              <div className="relative px-5 pt-5 pb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{
                        background: `radial-gradient(circle, ${isAlert ? 'rgba(255,34,68,0.2)' : `${colors.primary}20`} 0%, transparent 70%)`,
                        border: `1px solid ${isAlert ? '#ff2244' : colors.primary}40`,
                        boxShadow: `0 0 12px ${isAlert ? 'rgba(255,34,68,0.2)' : `${colors.primary}30`}`,
                      }}
                    >
                      <Icon
                        size={14}
                        style={{ color: isAlert ? '#ff2244' : colors.primary }}
                      />
                    </div>
                    <div>
                      <h3
                        className="font-mono text-[0.6rem] tracking-[0.25em] uppercase font-medium"
                        style={{ color: isAlert ? '#ff2244' : colors.primary }}
                      >
                        <GlitchText active={isAlert}>{panel.title}</GlitchText>
                      </h3>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <Clock size={8} className="text-gray-600" />
                        <span className="font-mono text-[0.5rem] text-gray-600 tracking-wider">
                          {new Date(panel.timestamp).toLocaleTimeString('en-US', {
                            hour12: false,
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                          })}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div
                className={`px-5 pb-5 font-light text-sm leading-relaxed ${
                  panel.type === 'code' || panel.type === 'command'
                    ? 'font-mono text-xs text-emerald-300/80'
                    : 'text-gray-300/90'
                }`}
                style={{
                  maxHeight: idx === 0 ? '200px' : '120px',
                  overflow: 'hidden',
                }}
              >
                {panel.content}
              </div>

              {/* Bottom gradient fade */}
              <div
                className="absolute bottom-0 left-0 right-0 h-8 pointer-events-none"
                style={{
                  background: `linear-gradient(to top, rgba(0,0,0,0.8), transparent)`,
                }}
              />
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* System info sidebar - right edge */}
      <AnimatePresence>
        {state !== 'idle' && (
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 0.6, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            className="flex flex-col gap-2 items-end"
          >
            {['SCANNING', 'PROCESSING', 'SYNCHRONIZING'].map((label, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: [0, 0.7, 0], x: [20, 0, -20] }}
                transition={{
                  repeat: Infinity,
                  duration: 2,
                  delay: i * 0.4,
                  ease: 'easeInOut',
                }}
                className="flex items-center gap-2"
              >
                <span className="font-mono text-[0.5rem] tracking-[0.2em] text-gray-600">{label}</span>
                <div
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    background: colors.primary,
                    boxShadow: `0 0 6px ${colors.primary}`,
                  }}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
