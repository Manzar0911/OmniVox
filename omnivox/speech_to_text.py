"""Open-source Speech-to-Text module for OmniVox."""
import os
import tempfile

from .logging_utils import log_stage


def transcribe_audio(file_path: str) -> str:
    """Transcribe a local audio file to text using open-source speech recognition."""
    log_stage("Mic -> STT", input=f"<audio file: {file_path}>")

    try:
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError:
        print("[STT] speech_recognition or pydub not installed.")
        return ""

    recognizer = sr.Recognizer()

    wav_path = None
    try:
        # Convert any audio container (webm/mp4/ogg) to 16kHz mono WAV for recognition
        sound = AudioSegment.from_file(file_path)
        sound = sound.set_channels(1).set_frame_rate(16000)
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        
        sound.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            text = text.strip()
            log_stage("STT -> Orchestrator", output=text)
            return text
    except sr.UnknownValueError:
        print("[STT] Could not understand audio")
        return ""
    except Exception as exc:
        print(f"[STT] Recognition error: {exc}")
        return ""
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
