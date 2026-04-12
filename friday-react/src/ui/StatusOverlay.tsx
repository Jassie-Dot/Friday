import { useAIStore } from '../core/store';
import { Mic, Activity, CheckCircle2, WifiOff, Cpu, Zap } from 'lucide-react';
import { motion } from 'framer-motion';


const STATE_COLORS = {
  idle: { primary: '#00d4ff', secondary: '#613187', glow: 'rgba(0, 212, 255, 0.3)' },
  listening: { primary: '#00ffff', secondary: '#8000ff', glow: 'rgba(0, 255, 255, 0.4)' },
  thinking: { primary: '#3366ff', secondary: '#ff13cc', glow: 'rgba(51, 102, 255, 0.5)' },
  responding: { primary: '#22ffcc', secondary: '#00ff80', glow: 'rgba(34, 255, 204, 0.4)' },
  error: { primary: '#ff2244', secondary: '#ff8000', glow: 'rgba(255, 34, 68, 0.5)' },
};

export function StatusOverlay() {
  const state = useAIStore((s) => s.state);
  const audioLevel = useAIStore((s) => s.audioLevel);
  const connectionStatus = useAIStore((s) => s.connectionStatus);

  const colors = STATE_COLORS[state] || STATE_COLORS.idle;

  return (
    <div className="absolute inset-0 pointer-events-none z-20 flex flex-col justify-between p-6">

      {/* Top Banner */}
      <header className="flex justify-between items-start w-full">
        {/* FRIDAY Logo */}
        <div className="flex items-center gap-4">
          <div className="relative flex items-center justify-center w-14 h-14">
            {/* Animated outer ring */}
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 8, ease: 'linear' }}
              className="absolute inset-0 border border-glow-blue/30 rounded-full"
              style={{ borderTopColor: colors.primary, borderRightColor: 'transparent' }}
            />
            {/* Pulsing core */}
            <motion.div
              animate={{
                scale: [1, 1.15, 1],
                boxShadow: [
                  `0 0 15px ${colors.primary}`,
                  `0 0 40px ${colors.glow}`,
                  `0 0 15px ${colors.primary}`
                ]
              }}
              transition={{ repeat: Infinity, duration: 2 + (state === 'thinking' ? 0.3 : 0), ease: 'easeInOut' }}
              className="absolute w-9 h-9 rounded-full"
              style={{ background: `radial-gradient(circle at 30% 30%, ${colors.primary}, ${colors.secondary})` }}
            />
            {/* Inner bright spot */}
            <div
              className="w-3 h-3 rounded-full bg-white/80"
              style={{ boxShadow: `0 0 15px ${colors.primary}, 0 0 30px ${colors.primary}` }}
            />
          </div>

          <div className="flex flex-col">
            <h1
              className="font-sans font-bold tracking-[0.3em] text-sm"
              style={{ color: colors.primary, textShadow: `0 0 10px ${colors.glow}` }}
            >
              FRIDAY
            </h1>
            <span className="text-xs text-gray-500 font-mono tracking-[0.2em] uppercase">System Core v2.0</span>
          </div>
        </div>

        {/* Status Indicators */}
        <motion.div
          className="flex items-center gap-4 px-5 py-3 rounded-xl"
          style={{
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(12px)',
            border: `1px solid ${colors.primary}22`,
            boxShadow: `0 0 20px ${colors.glow}20, inset 0 0 20px ${colors.glow}10`
          }}
          animate={{ borderColor: `${colors.primary}44` }}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          {/* Connection status */}
          <div className="flex items-center gap-2">
            {connectionStatus === 'connected' ? (
              <motion.div animate={{ opacity: [1, 0.5, 1] }} transition={{ repeat: Infinity, duration: 2 }}>
                <CheckCircle2 size={14} style={{ color: colors.primary }} />
              </motion.div>
            ) : connectionStatus === 'connecting' ? (
              <motion.div animate={{ opacity: [1, 0.3, 1], scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1 }}>
                <Activity size={14} className="text-yellow-500" />
              </motion.div>
            ) : (
              <WifiOff size={14} className="text-red-500" />
            )}
            <span
              className="font-mono text-[0.6rem] tracking-[0.2em] text-gray-400"
              style={{ color: connectionStatus === 'connected' ? colors.primary : undefined }}
            >
              {connectionStatus.toUpperCase()}
            </span>
          </div>

          <div className="h-5 w-px bg-white/10" />

          {/* CPU indicator */}
          <div className="flex items-center gap-2">
            <Cpu size={12} style={{ color: colors.primary }} className="opacity-70" />
            <span className="font-mono text-[0.6rem] tracking-[0.15em] text-gray-500">CORE</span>
          </div>

          <div className="h-5 w-px bg-white/10" />

          {/* State indicator with glow */}
          <div className="flex items-center gap-2">
            <motion.div
              animate={{
                boxShadow: [
                  `0 0 5px ${colors.primary}`,
                  `0 0 15px ${colors.glow}`,
                  `0 0 5px ${colors.primary}`
                ]
              }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className="w-2 h-2 rounded-full"
              style={{ background: colors.primary }}
            />
            <span
              className="font-mono text-[0.65rem] tracking-[0.2em] font-medium"
              style={{ color: colors.primary, textShadow: `0 0 8px ${colors.glow}` }}
            >
              {state.toUpperCase()}
            </span>
          </div>

          <div className="h-5 w-px bg-white/10" />

          {/* Energy indicator */}
          <div className="flex items-center gap-2">
            <Zap size={12} style={{ color: colors.primary }} className="opacity-70" />
            <div className="w-12 h-1.5 rounded-full bg-white/10 overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{
                  background: `linear-gradient(90deg, ${colors.secondary}, ${colors.primary})`,
                  boxShadow: `0 0 8px ${colors.primary}`
                }}
                animate={{
                  width: state === 'thinking' ? '75%' : state === 'responding' ? `${20 + audioLevel * 60}%` : state === 'listening' ? `${30 + audioLevel * 40}%` : '25%'
                }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        </motion.div>
      </header>

      {/* Voice Activity UI - Bottom */}
      <footer className="w-full flex justify-center pb-10">
        <div className="flex flex-col items-center gap-5">
          {/* Voice rings */}
          <div className="relative flex items-center justify-center">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                animate={{
                  scale: state === 'listening'
                    ? [1 + audioLevel * (1.5 + i * 0.5), 1.5 + audioLevel * (2 + i)]
                    : [1, 1.05, 1],
                  opacity: state === 'listening'
                    ? [0.1 + audioLevel * 0.3, 0.05 + audioLevel * 0.1]
                    : [0.05, 0.1, 0.05],
                  borderColor: colors.primary,
                }}
                transition={{
                  repeat: Infinity,
                  duration: 1.5 + i * 0.3,
                  ease: 'easeInOut',
                }}
                className="absolute w-20 h-20 rounded-full border"
                style={{ borderColor: `${colors.primary}40` }}
              />
            ))}

            {/* Center mic */}
            <motion.div
              className="w-16 h-16 rounded-full flex items-center justify-center"
              style={{
                background: state === 'listening'
                  ? `radial-gradient(circle, ${colors.glow} 0%, rgba(0,0,0,0.8) 70%)`
                  : 'rgba(0,0,0,0.6)',
                backdropFilter: 'blur(8px)',
                border: `2px solid ${colors.primary}60`,
                boxShadow: `0 0 30px ${colors.glow}40`
              }}
              animate={{
                borderColor: state === 'listening' ? `${colors.primary}cc` : `${colors.primary}40`,
              }}
            >
              <Mic
                size={22}
                style={{
                  color: state === 'listening' ? colors.primary : '#666',
                  filter: state === 'listening' ? `drop-shadow(0 0 8px ${colors.primary})` : 'none',
                }}
              />
            </motion.div>
          </div>

          {/* Status text */}
          <motion.p
            className="font-mono text-[0.6rem] tracking-[0.15em] text-gray-500 text-center w-72 opacity-70"
            animate={{ opacity: state === 'listening' ? 1 : 0.5 }}
            style={{ color: state === 'listening' ? colors.primary : undefined }}
          >
            {state === 'idle' ? (
              <>
                SAY 'HEY FRIDAY' TO ACTIVATE
                <br />
                <span className="text-gray-600 text-[0.5rem]">or type your request below</span>
              </>
            ) : state === 'listening' ? (
              <>
                <motion.span
                  animate={{ opacity: [1, 0.5, 1] }}
                  transition={{ repeat: Infinity, duration: 0.8 }}
                >
                  PROCESSING AUDIO
                </motion.span>
              </>
            ) : state === 'thinking' ? (
              <>
                <motion.span
                  animate={{ opacity: [0.6, 1, 0.6] }}
                  transition={{ repeat: Infinity, duration: 1.2 }}
                >
                  ANALYZING & REASONING
                </motion.span>
              </>
            ) : state === 'responding' ? (
              <>SPEAKING RESPONSE</>
            ) : (
              <>SYSTEM FAULT DETECTED</>
            )}
          </motion.p>
        </div>
      </footer>
    </div>
  );
}
