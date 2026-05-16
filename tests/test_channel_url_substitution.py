"""Unit tests for substitute_channel_placeholders used at upload time."""
from console.backend.tasks.youtube_upload_task import substitute_channel_placeholders


URL = "https://www.youtube.com/@AmbientEarth-n9h"


def test_replaces_full_placeholder():
    desc = "Relax to 8 hours of ambience.\n\n[Add links to other work ambience videos in your channel here]\n\n#ambient"
    out = substitute_channel_placeholders(desc, URL)
    assert "[Add links" not in out
    assert URL in out
    # surrounding context preserved
    assert out.startswith("Relax to 8 hours")
    assert out.endswith("#ambient")


def test_replaces_short_placeholder_variant():
    desc = "Subscribe! [Add link to your channel here]"
    out = substitute_channel_placeholders(desc, URL)
    assert out == f"Subscribe! {URL}"


def test_replaces_multiple_placeholders():
    desc = "[Add links to your channel videos] and [more videos in your channel]"
    out = substitute_channel_placeholders(desc, URL)
    assert out == f"{URL} and {URL}"


def test_case_insensitive_match():
    desc = "[ADD LINKS TO YOUR CHANNEL HERE]"
    out = substitute_channel_placeholders(desc, URL)
    assert out == URL


def test_leaves_unrelated_brackets_alone():
    desc = "Music by [Artist Name]. Find more music [on Spotify]."
    out = substitute_channel_placeholders(desc, URL)
    assert out == desc


def test_keeps_placeholder_when_url_missing():
    desc = "[Add links to videos in your channel here]"
    out = substitute_channel_placeholders(desc, None)
    assert out == desc
    out2 = substitute_channel_placeholders(desc, "")
    assert out2 == desc


def test_handles_empty_description():
    assert substitute_channel_placeholders("", URL) == ""
    assert substitute_channel_placeholders(None, URL) == ""


def test_does_not_replace_brackets_without_your_channel_phrase():
    """Only the exact 'your channel' phrase (case-insensitive) triggers
    substitution; generic 'channel' references stay."""
    desc = "[Visit the channel] and [Other channels worth subscribing to]"
    out = substitute_channel_placeholders(desc, URL)
    assert out == desc
