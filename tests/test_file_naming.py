import pytest
from datetime import date
from pathlib import Path
from console.backend.utils.file_naming import make_filename, make_unique_path


FIXED_DATE = date(2026, 5, 9)


def test_make_filename_ascii():
    result = make_filename("Distant Izakaya Laughter — Very Muffled", ".mp3", FIXED_DATE)
    assert result == "20260509_distant-izakaya-laughter-very-muffled.mp3"


def test_make_filename_vietnamese():
    result = make_filename("Tiếng mưa rơi trên mái hiên gần", ".mp3", FIXED_DATE)
    assert result == "20260509_tieng-mua-roi-tren-mai-hien-gan.mp3"


def test_make_filename_ampersand():
    result = make_filename("City Rain & Distant Trains", ".mp3", FIXED_DATE)
    assert result == "20260509_city-rain-and-distant-trains.mp3"


def test_make_filename_long_dash():
    result = make_filename("Rainy Tokyo Night Ambience — City Rain", ".mp3", FIXED_DATE)
    assert result == "20260509_rainy-tokyo-night-ambience-city-rain.mp3"


def test_make_filename_no_ext():
    result = make_filename("Rainy Tokyo Night", "", FIXED_DATE)
    assert result == "20260509_rainy-tokyo-night"


def test_make_filename_defaults_to_today():
    result = make_filename("test", ".wav")
    today = date.today().strftime("%Y%m%d")
    assert result.startswith(today)


def test_make_filename_empty_title():
    result = make_filename("", ".mp3", FIXED_DATE)
    assert result == "20260509_untitled.mp3"


def test_make_unique_path_no_collision(tmp_path):
    p = make_unique_path("Rain Loop", ".mp3", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rain-loop.mp3"


def test_make_unique_path_collision(tmp_path):
    (tmp_path / "20260509_rain-loop.mp3").touch()
    p = make_unique_path("Rain Loop", ".mp3", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rain-loop_2.mp3"


def test_make_unique_path_multiple_collisions(tmp_path):
    (tmp_path / "20260509_rain-loop.mp3").touch()
    (tmp_path / "20260509_rain-loop_2.mp3").touch()
    p = make_unique_path("Rain Loop", ".mp3", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rain-loop_3.mp3"


def test_make_unique_path_directory(tmp_path):
    p = make_unique_path("Rainy Tokyo Night", "", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rainy-tokyo-night"
