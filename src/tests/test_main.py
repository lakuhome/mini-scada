from src.main import run_self_check, VERSION


def test_main_self_check():
    """Проверка того, что процедура самодиагностики отрабатывает успешно и возвращает 0."""
    exit_code = run_self_check()
    assert exit_code == 0


def test_version_format():
    """Проверка формата версии продукта под КТ-1."""
    assert "kt1" in VERSION
