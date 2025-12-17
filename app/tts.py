import io
from groq import Groq


def synthesize_speech(text: str, api_key: str) -> bytes:
    """Convert text to speech using PlayAI TTS."""
    if not text:
        raise ValueError("No text provided for speech synthesis")
    client = Groq(api_key=api_key)
    try:
        audio = client.audio.speech.create(
            model="playai-tts",
            voice="Aaliyah-PlayAI",
            response_format="wav",
            input=text,
        )
        return audio.read()
    except Exception as e:
        msg = str(e)
        if "model_terms_required" in msg or "terms acceptance" in msg.lower():
            raise RuntimeError(
                "TTS model requires terms acceptance. Please accept terms for playai-tts at "
                "https://console.groq.com/playground?model=playai-tts"
            ) from e
        raise


