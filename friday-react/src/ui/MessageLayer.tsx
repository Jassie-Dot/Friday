import { motion, AnimatePresence } from 'framer-motion';
import { useAIStore } from '../core/store';

const STATE_COLORS = {
  idle: { primary: '#00d4ff', secondary: '#613187', glow: 'rgba(0, 212, 255, 0.6)' },
  listening: { primary: '#00ffff', secondary: '#8000ff', glow: 'rgba(0, 255, 255, 0.6)' },
  thinking: { primary: '#3366ff', secondary: '#ff13cc', glow: 'rgba(51, 102, 255, 0.6)' },
  responding: { primary: '#22ffcc', secondary: '#00ff80', glow: 'rgba(34, 255, 204, 0.6)' },
  error: { primary: '#ff2244', secondary: '#ff8000', glow: 'rgba(255, 34, 68, 0.6)' },
};

export function MessageLayer() {
  const messages = useAIStore((s) => s.messages);
  const state = useAIStore((s) => s.state);

  return (
    <div className="absolute inset-0 pointer-events-none flex flex-col justify-center items-center gap-8 z-10 overflow-hidden p-12">
      <AnimatePresence mode="popLayout">
        {messages.map((msg, idx) => {
          const revIdx = messages.length - 1 - idx;
          const isNewest = revIdx === 0;
          const isFriday = msg.role === 'friday';
          const msgColors = isFriday ? STATE_COLORS[state] : { primary: '#888', secondary: '#444', glow: 'rgba(136, 136, 136, 0.3)' };

          return (
            <motion.div
              layout
              key={msg.id}
              initial={{
                opacity: 0,
                y: 60,
                scale: 0.7,
                rotateX: 20,
                filter: 'blur(12px)',
              }}
              animate={{
                opacity: isNewest ? 1 : Math.max(0.15, 0.8 - revIdx * 0.25),
                y: 0,
                scale: isNewest ? 1 : Math.max(0.85, 1 - revIdx * 0.04),
                rotateX: isNewest ? 0 : -6 * revIdx,
                filter: isNewest ? 'blur(0px)' : `blur(${Math.min(revIdx * 1.5, 6)}px)`,
              }}
              exit={{
                opacity: 0,
                scale: 1.15,
                y: -40,
                filter: 'blur(12px)',
              }}
              transition={{
                type: 'spring',
                stiffness: 180,
                damping: 22,
                mass: 0.8,
              }}
              className="relative max-w-3xl text-center px-8"
              style={{ perspective: 1000 }}
            >
              {/* Glow backdrop */}
              {isFriday && (
                <motion.div
                  className="absolute inset-0 rounded-2xl"
                  animate={{
                    opacity: isNewest ? 0.15 : 0,
                    scale: isNewest ? 1 : 0.95,
                  }}
                  style={{
                    background: `radial-gradient(ellipse at center, ${msgColors.glow} 0%, transparent 70%)`,
                    filter: 'blur(30px)',
                    zIndex: -1,
                  }}
                />
              )}

              {/* Label */}
              <div
                className="text-[0.55rem] uppercase tracking-[0.35em] font-mono mb-3 opacity-60"
                style={{ color: msgColors.primary }}
              >
                {isFriday ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="inline-block w-2 h-px" style={{ background: msgColors.primary }} />
                    FRIDAY
                    <span className="inline-block w-2 h-px" style={{ background: msgColors.primary }} />
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <span className="inline-block w-2 h-px bg-gray-500" />
                    YOU
                    <span className="inline-block w-2 h-px bg-gray-500" />
                  </span>
                )}
              </div>

              {/* Message text */}
              <div
                className="text-xl md:text-2xl font-light leading-relaxed tracking-wide"
                style={{
                  color: msgColors.primary,
                  textShadow: isFriday
                    ? `0 0 20px ${msgColors.glow}, 0 0 40px ${msgColors.glow}50`
                    : 'none',
                }}
              >
                {msg.text}
              </div>

              {/* Underline glow for newest */}
              {isNewest && isFriday && (
                <motion.div
                  className="absolute -bottom-2 left-1/2 h-px rounded-full"
                  animate={{
                    width: ['30%', '60%', '30%'],
                    opacity: [0.4, 0.8, 0.4],
                    x: '-50%',
                  }}
                  transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
                  style={{
                    background: `linear-gradient(90deg, transparent, ${msgColors.primary}, transparent)`,
                    boxShadow: `0 0 10px ${msgColors.primary}`,
                  }}
                />
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
