import { useAIStore } from './store';
import { submitObjectiveToServer } from './socket';

const spokenTexts = new Set<string>();

// ── TTS ──
export function speakText(text: string) {
  if (!text || !window.speechSynthesis) return;

  const textKey = text.substring(0, 100);
  if (spokenTexts.has(textKey)) return;
  spokenTexts.add(textKey);
  if (spokenTexts.size > 50) {
    const first = spokenTexts.values().next().value;
    spokenTexts.delete(first as string);
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  
  const voices = window.speechSynthesis.getVoices();
  const preferredVoice =
    voices.find(v => /irish/i.test(v.name) && /female/i.test(v.name)) ||
    voices.find(v => /uk english female/i.test(v.name)) ||
    voices.find(v => /zira/i.test(v.name)) ||
    voices.find(v => /female/i.test(v.name)) ||
    voices[0];

  if (preferredVoice) utterance.voice = preferredVoice;
  utterance.pitch = 1.05;
  utterance.rate = 1.05;

  utterance.onstart = () => {
    useAIStore.getState().setState('responding');
  };

  window.speechSynthesis.speak(utterance);
}

// ── Voice Input & Audio Level ──
export function initVoiceSystem() {
  const SRecogniton = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  
  if (SRecogniton) {
    const recognition = new SRecogniton();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event: any) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        }
      }

      if (finalTranscript) {
        const cleaned = finalTranscript.trim();
        const wakeWordPattern = /^(hey\s+)?friday[,.\s]*/i;
        const match = cleaned.match(wakeWordPattern);

        if (match) {
          const command = cleaned.replace(wakeWordPattern, '').trim();
          submitObjectiveToServer(command || 'Hello');
        }
      }
    };

    recognition.onerror = (e: any) => {
      if (e.error === 'no-speech' || e.error === 'aborted') {
        setTimeout(() => { try { recognition.start(); } catch {} }, 300);
      }
    };
    
    recognition.onend = () => {
      setTimeout(() => { try { recognition.start(); } catch {} }, 300);
    };

    try { recognition.start(); } catch {}
  }

  // Audio Analyzer
  navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Uint8Array(analyser.frequencyBinCount);
    
    const update = () => {
      analyser.getByteFrequencyData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i];
      useAIStore.getState().setAudioLevel((sum / buf.length) / 255);
      requestAnimationFrame(update);
    };
    update();
  }).catch(() => console.warn('Audio visualization unavailable'));
}
