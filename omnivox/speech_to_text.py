"""Open-source Speech-to-Text module for OmniVox."""
import os
import subprocess
import tempfile

from .logging_utils import log_stage


def _convert_to_wav(input_path: str, output_path: str) -> bool:
    """Convert input audio file to 16kHz mono WAV using imageio_ffmpeg or system ffmpeg."""
    ffmpeg_exe = "ffmpeg"
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        output_path,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as exc:
        # If conversion fails or ffmpeg is not found, fallback to pydub if available
        try:
            from pydub import AudioSegment
            sound = AudioSegment.from_file(input_path)
            sound = sound.set_channels(1).set_frame_rate(16000)
            sound.export(output_path, format="wav")
            return True
        except Exception:
            return False


def transcribe_audio(file_path: str) -> str:
    """Transcribe a local audio file to text using speech recognition."""
    log_stage("Mic -> STT", input=f"<audio file: {file_path}>")

    try:
        import speech_recognition as sr
    except ImportError:
        print("[STT] speech_recognition not installed.")
        return ""

    recognizer = sr.Recognizer()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        converted = _convert_to_wav(file_path, wav_path)
        source_path = wav_path if converted else file_path

        with sr.AudioFile(source_path) as source:
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
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
