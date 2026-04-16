from pathlib import Path

from app.common.i18n import I18nService


def test_i18n_ru_en_resolution() -> None:
    i18n = I18nService(Path("locales"), default_locale="ru")
    assert "Пациент" in i18n.t("role.patient.home", "ru")
    assert "Patient" in i18n.t("role.patient.home", "en")
    assert "Доступ запрещён" in i18n.t("access.denied.role", "ru")
    assert "Access denied" in i18n.t("access.denied.role", "en")
    assert i18n.t("missing.key", "en") == "missing.key"
