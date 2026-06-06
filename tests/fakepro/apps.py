from django.apps import AppConfig


class FakeProConfig(AppConfig):
    name = "tests.fakepro"
    label = "fakepro"
    default_auto_field = "django.db.models.BigAutoField"
