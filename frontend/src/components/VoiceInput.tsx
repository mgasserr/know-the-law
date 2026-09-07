import React, { useRef, useState, useEffect } from 'react';
import { MdMic, MdMicOff, MdStop } from 'react-icons/md';
import { AudioRecorder } from '@/utils/audioRecorder';
import { chatbotAPI } from '@/services/chatbotAPI';
import styles from './VoiceInput.module.css';

interface VoiceInputProps {
  onTranscriptionComplete: (text: string) => void;
  disabled?: boolean;
}

const VoiceInput: React.FC<VoiceInputProps> = ({ onTranscriptionComplete, disabled = false }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [micAvailable, setMicAvailable] = useState(true);
  const recorderRef = useRef<AudioRecorder | null>(null);

  useEffect(() => {
    // Check microphone availability on mount
    AudioRecorder.checkMicrophoneAccess().then(setMicAvailable);
  }, []);

  const handleStartRecording = async () => {
    if (!micAvailable || disabled) return;

    try {
      setError(null);
      if (!recorderRef.current) {
        recorderRef.current = new AudioRecorder();
      }

      await recorderRef.current.startRecording();
      setIsRecording(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start recording');
      setMicAvailable(false);
    }
  };

  const handleStopRecording = async () => {
    if (!recorderRef.current) return;

    try {
      setIsRecording(false);
      setIsProcessing(true);
      setError(null);

      const audioBlob = await recorderRef.current.stopRecording();
      const transcript = await chatbotAPI.transcribeAudio(audioBlob);

      onTranscriptionComplete(transcript);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to transcribe audio');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCancelRecording = () => {
    if (recorderRef.current) {
      recorderRef.current.cancelRecording();
    }
    setIsRecording(false);
    setError(null);
  };

  if (!micAvailable) {
    return (
      <div className={styles.voiceInputWrapper}>
        <button
          className={styles.voiceButton}
          disabled={true}
          title="الميكروفون غير متاح"
        >
          <MdMicOff size={20} />
        </button>
        <span className={styles.errorMessage}>الميكروفون غير متاح</span>
      </div>
    );
  }

  return (
    <div className={styles.voiceInputWrapper}>
      {!isRecording ? (
        <button
          className={`${styles.voiceButton} ${disabled ? styles.disabled : ''}`}
          onClick={handleStartRecording}
          disabled={disabled || isProcessing}
          title="اضغط للبدء في التسجيل"
          aria-label="تسجيل صوتي"
        >
          {isProcessing ? <MdMic size={20} className={styles.pulse} /> : <MdMic size={20} />}
        </button>
      ) : (
        <div className={styles.recordingControls}>
          <button
            className={`${styles.voiceButton} ${styles.stopButton}`}
            onClick={handleStopRecording}
            disabled={isProcessing}
            title="انقر للتوقف"
            aria-label="إيقاف التسجيل"
          >
            <MdStop size={20} />
          </button>
          <button
            className={`${styles.voiceButton} ${styles.cancelButton}`}
            onClick={handleCancelRecording}
            disabled={isProcessing}
            title="إلغاء التسجيل"
            aria-label="إلغاء التسجيل"
          >
            ✕
          </button>
          <span className={styles.recordingIndicator}>
            <span className={styles.recordingDot}></span>
            جاري التسجيل...
          </span>
        </div>
      )}

      {error && (
        <div className={styles.errorMessage}>
          {error}
          <button
            className={styles.closeError}
            onClick={() => setError(null)}
          >
            ✕
          </button>
        </div>
      )}

      {isProcessing && (
        <div className={styles.processingMessage}>
          جاري معالجة الصوت...
        </div>
      )}
    </div>
  );
};

export default VoiceInput;
