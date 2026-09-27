"""Open-source Text-to-Speech synthesis module for OmniVox."""
import asyncio
import os
import re
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


def clean_text_for_speech(text: str) -> str:
    """Strip markdown formatting, asterisks, raw URLs, and symbols so speech sounds natural."""
    if not text:
        return ""
    # Strip markdown links [label](url) -> label
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Strip angle-bracketed emails/URLs <email@example.com> -> ""
    text = re.sub(r'<[^>]+>', r'', text)
    # Strip markdown bold / italics asterisks and underscores
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Strip header hashes (#), bullet asterisks (*), dashes (-), blockquotes (>) at start of line
    text = re.sub(r'^[ \t]*[#*\-•>]+[ \t]*', '', text, flags=re.MULTILINE)
    # Remove any leftover formatting symbols
    text = text.replace('*', '').replace('#', '').replace('~', '').replace('`', '')
    # Normalize whitespace and turn multiple linebreaks into sentence pauses
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', '. ', text)
    return text.strip()


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
    spoken_text = clean_text_for_speech(text)
    if not spoken_text:
        return ""

    from .cache import audio_cache

    # 1. Check audio cache (sub-millisecond instant hit)
    cached_audio = audio_cache.get_audio_file(spoken_text, _DEFAULT_VOICE)
    if cached_audio:
        log_stage("AudioCache -> Speaker (HIT)", voice=_DEFAULT_VOICE)
        return cached_audio

    log_stage("Orchestrator -> TTS (MISS)", input=spoken_text)

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
                pool.submit(lambda: asyncio.run(_synthesize_edge_tts(spoken_text, tmp_path, _DEFAULT_VOICE))).result()
        else:
            loop.run_until_complete(_synthesize_edge_tts(spoken_text, tmp_path, _DEFAULT_VOICE))

        cached_path = audio_cache.set_audio_file(spoken_text, _DEFAULT_VOICE, tmp_path)
        log_stage("TTS -> Speaker", output=f"<audio file: {cached_path}>")
        return cached_path
    except Exception as exc:
        print(f"[TTS] edge-tts error: {exc}")
        # Offline Windows pyttsx3 fallback
        try:
            import pyttsx3
            engine = pyttsx3.init()
            wav_path = tmp_path.replace(".mp3", ".wav")
            engine.save_to_file(spoken_text, wav_path)
            engine.runAndWait()
            cached_path = audio_cache.set_audio_file(spoken_text, _DEFAULT_VOICE, wav_path)
            return cached_path
        except Exception as e:
            print(f"[TTS] pyttsx3 fallback failed: {e}")
            return ""


