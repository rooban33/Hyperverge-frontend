// components/AudioRecorderModal.tsx
"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Mic, StopCircle, Upload } from 'lucide-react';

interface AudioRecorderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRecordingComplete?: (blob: Blob) => void;
  onUploadSuccess?: (url: string) => void;
}

const AudioRecorderModal: React.FC<AudioRecorderModalProps> = ({ 
  isOpen, 
  onClose, 
  onRecordingComplete,
  onUploadSuccess
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioFileRef = useRef<File | null>(null);

  // Reset states when modal closes
  useEffect(() => {
    if (!isOpen) {
      setIsRecording(false);
      setAudioUrl(null);
      setRecordingTime(0);
      stopTimer();
    }
  }, [isOpen]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const audioUrl = URL.createObjectURL(audioBlob);
        setAudioUrl(audioUrl);
        
        // Convert blob to File
        const audioFile = new File([audioBlob], 'recording.webm', { type: 'audio/webm' });
        audioFileRef.current = audioFile;
        
        // Call the callback with the audio blob if provided
        onRecordingComplete?.(audioBlob);
        
        // Stop tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
        stopTimer();
      };

      mediaRecorder.start();
      setIsRecording(true);
      startTimer();
    } catch (error) {
      console.error('Error accessing microphone:', error);
      alert('Could not access microphone. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const startTimer = () => {
    setRecordingTime(0);
    timerRef.current = setInterval(() => {
      setRecordingTime(prev => prev + 1);
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  // Format time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleUpload = async () => {
    if (!audioFileRef.current) return;

    try {
      setIsUploading(true);

      const uploadedUrl = await uploadFile(audioFileRef.current);
      
      onUploadSuccess?.(uploadedUrl);
      
      alert('Audio uploaded successfully!');
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload audio.');
    } finally {
      setIsUploading(false);
    }
  };

  if (!isOpen) return null;

  async function uploadFile(file: File) {
    if (!file.type.startsWith('image/') && !file.type.startsWith('audio/') && !file.type.startsWith('video/')) {
        return ''
    }

    let presigned_url = '';

    try {
        // First, get a presigned URL for the file
        const presignedUrlResponse = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/file/presigned-url/create`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content_type: file.type
            })
        });

        if (!presignedUrlResponse.ok) {
            throw new Error('Failed to get presigned URL');
        }

        const presignedData = await presignedUrlResponse.json();

        console.log('Presigned url generated');
        presigned_url = presignedData.presigned_url;
    } catch (error) {
        console.error("Error getting presigned URL for file:", error);
    }

    if (!presigned_url) {
        // If we couldn't get a presigned URL, try direct upload to the backend
        try {
            console.log("Attempting direct upload to backend");

            // Create FormData for the file upload
            const formData = new FormData();
            formData.append('file', file, file.name);
            formData.append('content_type', file.type);

            // Upload directly to the backend
            const uploadResponse = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/file/upload-local`, {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error(`Failed to upload audio to backend: ${uploadResponse.status}`);
            }

            const uploadData = await uploadResponse.json();
            const file_static_path = uploadData.static_url;

            const static_url = `${process.env.NEXT_PUBLIC_BACKEND_URL}${file_static_path}`;

            console.log('File uploaded successfully to backend');
            console.log(static_url);

            return static_url;
        } catch (error) {
            console.error('Error with direct upload to backend:', error);
            throw error;
        }
    } else {
        // Upload the file to S3 using the presigned URL
        try {
            let fileBlob = new Blob([file], { type: file.type });

            // Upload to S3 using the presigned URL with WAV content type
            const uploadResponse = await fetch(presigned_url, {
                method: 'PUT',
                body: fileBlob,
                headers: {
                    'Content-Type': file.type
                }
            });

            if (!uploadResponse.ok) {
                throw new Error(`Failed to upload file to S3: ${uploadResponse.status}`);
            }

            console.log('File uploaded successfully to S3');
            console.log(uploadResponse);
            // Update the request body with the file information
            return uploadResponse.url
        } catch (error) {
            console.error('Error uploading file to S3:', error);
            throw error;
        }
    }
  }

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      onClick={onClose}
    >
      <div 
        className="bg-[#222] p-6 rounded-lg w-96 max-w-full text-white"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold mb-4 text-center">Audio Recorder</h2>
        
        {/* Recording Status */}
        <div className="text-center mb-4">
          <div className="text-yellow-400 text-lg">
            {isRecording ? 'Recording...' : audioUrl ? 'Recording Stopped' : 'Ready to Record'}
          </div>
          {isRecording && (
            <div className="text-yellow-300 text-md mt-2">
              {formatTime(recordingTime)}
            </div>
          )}
        </div>

        {/* Recording Controls */}
        <div className="flex justify-center space-x-4 mb-4">
          {!isRecording ? (
            <button
              onClick={startRecording}
              className="bg-yellow-500 text-black px-4 py-2 rounded-full hover:bg-yellow-600 flex items-center"
            >
              <Mic className="mr-2" /> Start Recording
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="bg-red-500 text-white px-4 py-2 rounded-full hover:bg-red-600 flex items-center"
            >
              <StopCircle className="mr-2" /> Stop Recording
            </button>
          )}
        </div>

        {/* Audio Playback */}
        {audioUrl && (
          <div className="mt-4 text-center space-y-2">
            <audio 
              src={audioUrl} 
              controls 
              className="w-full mb-2"
            />
            <div className="flex justify-center space-x-4">
              <a 
                href={audioUrl} 
                download="recording.webm"
                className="text-yellow-400 hover:underline"
              >
                Download Recording
              </a>
              <button
                onClick={handleUpload}
                disabled={isUploading}
                className={`
                  flex items-center px-4 py-2 rounded-full 
                  ${isUploading 
                    ? 'bg-gray-500 cursor-not-allowed' 
                    : 'bg-green-500 hover:bg-green-600'
                  } text-white
                `}
              >
                {isUploading ? 'Uploading...' : (
                  <>
                    <Upload className="mr-2" /> Upload
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Close Button */}
        <div className="text-center mt-4">
          <button
            onClick={onClose}
            className="text-gray-300 hover:text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default AudioRecorderModal;