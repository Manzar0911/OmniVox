"""Open-source Text-to-Speech synthesis module for OmniVox."""
import asyncio
import os
import tempfile
import edge_tts

from .logging_utils import log_stage

_VOICE_MAP = {
    "alloy": "en-US-AriaNeural",
    "echo": "en-US-GuyNeural",
    "fable": "en-US-ChristopherNeural",
    "onyx": "en-US-EricNeural",
    "nova": "en-US-JennyNeural",
    "shimmer": "en-US-AnaNeural",
}

_RAW_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")
_DEFAULT_VOICE = _VOICE_MAP.get(_RAW_VOICE.lower(), _RAW_VOICE)


async def _synthesize_edge_tts(text: str, output_path: str, voice: str) -> None:
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
    except Exception:
        # Fallback to default Aria neural voice if custom voice is unsupported
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
        await communicate.save(output_path)


def synthesize_speech(text: str) -> str:
    """Convert text to spoken audio using neural TTS (zero cost)."""
    log_stage("Orchestrator -> TTS", input=text)
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(lambda: asyncio.run(_synthesize_edge_tts(text, tmp_path, _DEFAULT_VOICE))).result()
        else:
            loop.run_until_complete(_synthesize_edge_tts(text, tmp_path, _DEFAULT_VOICE))

        log_stage("TTS -> Speaker", output=f"<audio file: {tmp_path}>")
        return tmp_path
    except Exception as exc:
        print(f"[TTS] edge-tts error: {exc}")
        # Offline Windows pyttsx3 fallback
        try:
            import pyttsx3
            engine = pyttsx3.init()
            wav_path = tmp_path.replace(".mp3", ".wav")
            engine.save_to_file(text, wav_path)
            engine.runAndWait()
            return wav_path
        except Exception as e:
            print(f"[TTS] pyttsx3 fallback failed: {e}")
            return ""

