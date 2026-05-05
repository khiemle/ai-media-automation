import pytest
from unittest.mock import MagicMock, patch
from uploader.youtube_uploader import _build_tags, _build_description, _niche_to_category, set_thumbnail


def test_build_tags_always_has_shorts_first():
    tags = _build_tags({"hashtags": ["running", "fitness"], "niche": "running"})
    assert tags[0] == "Shorts"


def test_build_tags_no_duplicate_shorts():
    tags = _build_tags({"hashtags": ["Shorts", "running"], "niche": "running"})
    assert tags.count("Shorts") == 1


def test_build_tags_empty_metadata():
    tags = _build_tags({})
    assert tags[0] == "Shorts"


def test_build_description_appends_shorts_hashtag():
    desc = _build_description({"description": "Great run!", "hashtags": ["running"]})
    assert "#Shorts" in desc


def test_build_description_shorts_appended_when_no_hashtags():
    desc = _build_description({"description": "Great run!"})
    assert "#Shorts" in desc


def test_niche_to_category_running():
    assert _niche_to_category("running") == "17"


def test_niche_to_category_fitness():
    assert _niche_to_category("fitness") == "17"


def test_niche_to_category_unknown_defaults_to_people_blogs():
    assert _niche_to_category("unknown_niche") == "22"


def test_set_thumbnail_calls_thumbnails_set():
    mock_youtube = MagicMock()
    mock_creds = MagicMock()
    mock_creds.expired = False

    with patch("uploader.youtube_uploader.Credentials", return_value=mock_creds), \
         patch("uploader.youtube_uploader.build", return_value=mock_youtube), \
         patch("uploader.youtube_uploader.MediaFileUpload") as mock_media, \
         patch("pathlib.Path.exists", return_value=True):
        set_thumbnail(
            "abc123",
            "/tmp/thumb.png",
            {"access_token": "tok", "refresh_token": "ref", "client_id": "cid", "client_secret": "sec"},
        )

    mock_youtube.thumbnails().set.assert_called_once_with(
        videoId="abc123", media_body=mock_media.return_value
    )
    mock_youtube.thumbnails().set().execute.assert_called_once()


def test_set_thumbnail_forwards_video_id_to_api():
    mock_youtube = MagicMock()
    mock_creds = MagicMock()
    mock_creds.expired = False

    with patch("uploader.youtube_uploader.Credentials", return_value=mock_creds), \
         patch("uploader.youtube_uploader.build", return_value=mock_youtube), \
         patch("uploader.youtube_uploader.MediaFileUpload"), \
         patch("pathlib.Path.exists", return_value=True):
        set_thumbnail("my_video_id", "/tmp/thumb.png", {"access_token": "tok"})

    call_kwargs = mock_youtube.thumbnails().set.call_args[1]
    assert call_kwargs["videoId"] == "my_video_id"


def test_set_thumbnail_does_not_raise_on_api_error():
    mock_youtube = MagicMock()
    mock_youtube.thumbnails().set().execute.side_effect = RuntimeError("API down")
    mock_creds = MagicMock()
    mock_creds.expired = False

    with patch("uploader.youtube_uploader.Credentials", return_value=mock_creds), \
         patch("uploader.youtube_uploader.build", return_value=mock_youtube), \
         patch("uploader.youtube_uploader.MediaFileUpload"), \
         patch("pathlib.Path.exists", return_value=True):
        # Must not raise
        set_thumbnail("abc123", "/tmp/thumb.png", {"access_token": "tok"})
