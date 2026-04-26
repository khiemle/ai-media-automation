"""Lyria music generation via the Gemini API (google-genai SDK)."""
import base64
import os

try:
    from google import genai
except ImportError:
    genai = None

LYRIA_MODELS = {
    "lyria-clip": "lyria-3-clip-preview",
    "lyria-pro":  "lyria-3-pro-preview",
}


class LyriaProvider:
    def __init__(self):
        self._key = os.environ.get("GEMINI_MEDIA_API_KEY", "")
        if not self._key:
            raise RuntimeError("GEMINI_MEDIA_API_KEY is not set")
        if genai is None:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

    def generate(self, prompt: str, model: str, is_vocal: bool = False) -> tuple[bytes, str]:
        """
        Generate music and return (raw_audio_bytes, mime_type).

        model: 'lyria-3-clip-preview' (30s) or 'lyria-3-pro-preview' (full song)
        mime_type: e.g. 'audio/wav', 'audio/pcm', 'audio/L16;rate=44100'
        """
        vocal_suffix = " with vocals, sung lyrics" if is_vocal else " instrumental only, no vocals, no singing"
        full_prompt = prompt.strip() + vocal_suffix

        client = genai.Client(api_key=self._key)
        config = genai.types.GenerateContentConfig(
            response_modalities=["AUDIO"],
        )
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=config,
        )

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    mime_type = getattr(part.inline_data, "mime_type", "audio/wav") or "audio/wav"
                    return base64.b64decode(part.inline_data.data), mime_type

        raise RuntimeError("Lyria returned no audio data")
