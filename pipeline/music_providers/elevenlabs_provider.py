"""ElevenLabs music generation provider — composition plan + compose."""
import json

from config.api_config import get_config

try:
    from elevenlabs.client import ElevenLabs
except ImportError:
    ElevenLabs = None

# pcm/ulaw/alaw use .wav extension; ffprobe reads actual format, not extension
_FORMAT_TO_EXT = {
    "mp3":  ".mp3",
    "pcm":  ".wav",
    "opus": ".opus",
    "ulaw": ".wav",
    "alaw": ".wav",
}


def _ext_for_format(output_format: str) -> str:
    """Return file extension for a given output_format string (e.g. 'mp3_44100_192' → '.mp3')."""
    prefix = output_format.split("_")[0]
    return _FORMAT_TO_EXT.get(prefix, ".mp3")


class ElevenLabsProvider:
    def __init__(self):
        self._key = get_config()["elevenlabs"]["api_key"]
        if not self._key:
            raise RuntimeError("ElevenLabs API key is not configured in config/api_keys.json")
        if ElevenLabs is None:
            raise RuntimeError("elevenlabs not installed. Run: pip install elevenlabs")

    def create_plan(self, input_text: str, music_length_ms: int = 60000) -> dict:
        """
        Return a composition plan dict.
        If input_text is valid composition plan JSON (has 'sections' or
        'positive_global_styles'), return it as-is without calling the API.
        Otherwise call ElevenLabs to generate a plan from the text prompt.
        """
        try:
            parsed = json.loads(input_text)
            if isinstance(parsed, dict) and (
                "sections" in parsed or "positive_global_styles" in parsed
            ):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        client = ElevenLabs(api_key=self._key)
        plan = client.music.composition_plan.create(
            prompt=input_text,
            music_length_ms=music_length_ms,
        )
        if hasattr(plan, "model_dump"):
            return plan.model_dump()
        return dict(plan)

    def compose(
        self,
        plan: dict,
        output_format: str = "mp3_44100_192",
        respect_sections_durations: bool = True,
    ) -> bytes:
        """Generate audio from a composition plan. Returns raw audio bytes."""
        client = ElevenLabs(api_key=self._key)
        audio = client.music.compose(
            composition_plan=plan,
            respect_sections_durations=respect_sections_durations,
            output_format=output_format,
        )
        if isinstance(audio, bytes):
            return audio
        return b"".join(audio)
