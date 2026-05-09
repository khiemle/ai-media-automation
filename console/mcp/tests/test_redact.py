from console.mcp.redact import redact_args


def test_strips_token_field():
    assert redact_args({"id": 7, "api_token": "abc"}) == {"id": 7, "api_token": "***"}


def test_strips_key_and_password():
    out = redact_args({"client_key": "x", "password": "y", "name": "ok"})
    assert out == {"client_key": "***", "password": "***", "name": "ok"}


def test_recurses_into_dicts():
    out = redact_args({"creds": {"refresh_token": "t", "user": "u"}})
    assert out == {"creds": {"refresh_token": "***", "user": "u"}}


def test_recurses_into_lists():
    out = redact_args({"items": [{"oauth_token": "z"}, {"name": "a"}]})
    assert out == {"items": [{"oauth_token": "***"}, {"name": "a"}]}


def test_keeps_non_secret_fields_untouched():
    args = {"video_id": 12, "title": "Forest ASMR", "tags": ["sleep", "rain"]}
    assert redact_args(args) == args
