import pytest
from unittest.mock import patch, MagicMock


def test_script_update_schema_accepts_language():
    from console.backend.schemas.script import ScriptUpdate
    payload = ScriptUpdate(
        script_json={"meta": {}, "video": {}, "scenes": []},
        language="english",
    )
    assert payload.language == "english"


def test_script_update_schema_language_optional():
    from console.backend.schemas.script import ScriptUpdate
    payload = ScriptUpdate(script_json={"meta": {}, "video": {}, "scenes": []})
    assert payload.language is None


def test_update_script_saves_language():
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.status = "draft"
    mock_row.topic = None
    mock_row.niche = None
    mock_row.template = None
    mock_row.editor_notes = None
    mock_row.approved_at = None
    mock_row.performance_score = None
    mock_row.created_at = None
    mock_row.language = None
    mock_row.script_json = {"meta": {}, "video": {}, "scenes": []}

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_row

    with patch("console.backend.services.script_service.AuditLog"), \
         patch("console.backend.services.script_service.ScriptDetail") as mock_detail:
        mock_detail.model_validate.return_value = MagicMock(id=1)
        from console.backend.services.script_service import ScriptService
        svc = ScriptService(mock_db)
        svc.update_script(
            script_id=1,
            script_json={"meta": {}, "video": {}, "scenes": []},
            editor_notes=None,
            user_id=1,
            language="english",
        )

    assert mock_row.language == "english"


def test_update_script_skips_language_when_none():
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.status = "draft"
    mock_row.topic = None
    mock_row.niche = None
    mock_row.template = None
    mock_row.editor_notes = None
    mock_row.approved_at = None
    mock_row.performance_score = None
    mock_row.created_at = None
    mock_row.language = "vietnamese"
    mock_row.script_json = {"meta": {}, "video": {}, "scenes": []}

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_row

    with patch("console.backend.services.script_service.AuditLog"), \
         patch("console.backend.services.script_service.ScriptDetail") as mock_detail:
        mock_detail.model_validate.return_value = MagicMock(id=1)
        from console.backend.services.script_service import ScriptService
        svc = ScriptService(mock_db)
        svc.update_script(
            script_id=1,
            script_json={"meta": {}, "video": {}, "scenes": []},
            editor_notes=None,
            user_id=1,
            language=None,
        )

    assert mock_row.language == "vietnamese"


def test_generate_script_task_accepts_language():
    mock_script = MagicMock()
    mock_script.id = 99

    mock_svc = MagicMock()
    mock_svc.generate_script.return_value = mock_script

    mock_db = MagicMock()

    with patch("console.backend.tasks.script_tasks.SessionLocal", return_value=mock_db), \
         patch("console.backend.tasks.script_tasks.ScriptService", return_value=mock_svc):

        from console.backend.tasks.script_tasks import generate_script_task
        # __wrapped__ on a bind=True Celery task has no `self` parameter
        with patch.object(generate_script_task, 'update_state'):
            generate_script_task.__wrapped__(
                topic="test topic",
                niche="health",
                template="tiktok_viral",
                language="english",
            )

    mock_svc.generate_script.assert_called_once()
    call_kwargs = mock_svc.generate_script.call_args
    assert call_kwargs.kwargs.get("language") == "english" or \
           (call_kwargs.args and "english" in call_kwargs.args)
