import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Mic, Loader } from 'lucide-react';
import { submitObjectiveToServer } from '../core/socket';
import { useAIStore } from '../core/store';

const STATE_COLORS = {
  idle: { primary: '#00d4ff', glow: 'rgba(0, 212, 255, 0.3)' },
  listening: { primary: '#00ffff', glow: 'rgba(0, 255, 255, 0.4)' },
  thinking: { primary: '#3366ff', glow: 'rgba(51, 102, 255, 0.5)' },
  responding: { primary: '#22ffcc', glow: 'rgba(34, 255, 204, 0.4)' },
  error: { primary: '#ff2244', glow: 'rgba(255, 34, 68, 0.5)' },
};

export function InputBar() {
  const [text, setText] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const state = useAIStore((s) => s.state);
  const connectionStatus = useAIStore((s) => s.connectionStatus);
  const colors = STATE_COLORS[state] || STATE_COLORS.idle;

  const handleSubmit = () => {
    if (!text.trim() || connectionStatus !== 'connected') return;
    submitObjectiveToServer(text);
    setText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Focus on mount
  useEffect(() => {
    const timer = setTimeout(() => inputRef.current?.focus(), 500);
    return () => clearTimeout(timer);
  }, []);

  const isProcessing = state === 'thinking' || state === 'listening';

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 w-full max-w-2xl px-6">
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="relative"
        >
          {/* Glow backdrop when focused */}
          <motion.div
            animate={{
              opacity: isFocused ? 1 : 0,
              scale: isFocused ? 1.02 : 1,
            }}
            className="absolute inset-0 rounded-2xl blur-xl"
            style={{
              background: `radial-gradient(ellipse at center, ${colors.glow} 0%, transparent 70%)`,
            }}
          />

          {/* Main input container */}
          <div
            className="relative flex items-center gap-3 px-5 py-4 rounded-2xl overflow-hidden"
            style={{
              background: `rgba(2, 4, 10, 0.85)`,
              backdropFilter: 'blur(20px)',
              border: `1px solid ${isFocused ? `${colors.primary}50` : 'rgba(0, 212, 255, 0.15)'}`,
              boxShadow: `
                0 0 30px ${isFocused ? colors.glow : 'rgba(0, 0, 0, 0.5)'}40,
                inset 0 0 30px rgba(0, 0, 0, 0.3),
                0 20px 60px rgba(0, 0, 0, 0.4)
              `,
              transition: 'border-color 0.3s, box-shadow 0.3s',
            }}
          >
            {/* Animated border lines */}
            {isFocused && (
              <motion.div
                animate={{ opacity: [0.3, 0.7, 0.3] }}
                transition={{ repeat: Infinity, duration: 2 }}
                className="absolute top-0 left-0 right-0 h-px"
                style={{
                  background: `linear-gradient(90deg, transparent, ${colors.primary}, transparent)`,
                  boxShadow: `0 0 10px ${colors.primary}`,
                }}
              />
            )}

            {/* Mic indicator */}
            <div className="flex-shrink-0">
              {isProcessing ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                  className="w-5 h-5"
                >
                  <Loader size={18} style={{ color: colors.primary }} />
                </motion.div>
              ) : (
                <Mic
                  size={18}
                  style={{
                    color: isFocused ? colors.primary : '#444',
                    transition: 'color 0.3s',
                  }}
                  className="opacity-60"
                />
              )}
            </div>

            {/* Text input */}
            <input
              ref={inputRef}
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              disabled={connectionStatus !== 'connected' || isProcessing}
              placeholder={
                connectionStatus !== 'connected'
                  ? 'Reconnecting to FRIDAY...'
                  : state === 'thinking'
                  ? 'Processing your request...'
                  : 'Tell FRIDAY what you need...'
              }
              className="flex-1 bg-transparent text-sm font-light tracking-wide text-gray-200 placeholder-gray-600 outline-none disabled:cursor-not-allowed"
              style={{ caretColor: colors.primary }}
            />

            {/* Send button */}
            <motion.button
              onClick={handleSubmit}
              disabled={!text.trim() || connectionStatus !== 'connected' || isProcessing}
              className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
              style={{
                background: text.trim() ? `${colors.primary}20` : 'transparent',
                border: `1px solid ${text.trim() ? `${colors.primary}40` : 'transparent'}`,
                transition: 'all 0.2s',
              }}
              whileHover={text.trim() ? { scale: 1.1 } : {}}
              whileTap={text.trim() ? { scale: 0.92 } : {}}
            >
              <Send
                size={14}
                style={{
                  color: text.trim() ? colors.primary : '#444',
                  transform: 'rotate(0deg)',
                }}
              />
            </motion.button>
          </div>

          {/* Character count indicator */}
          {text.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="absolute -top-5 right-3 font-mono text-[0.5rem] text-gray-600 tracking-wider"
            >
              {text.length}/500
            </motion.div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Keyboard shortcut hint */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.4 }}
        transition={{ delay: 1 }}
        className="text-center mt-2 font-mono text-[0.5rem] tracking-[0.2em] text-gray-600"
      >
        PRESS ENTER TO SEND
      </motion.div>
    </div>
  );
}
