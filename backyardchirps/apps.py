from django.apps import AppConfig


class BackyardChirpsConfig(AppConfig):
    name = "backyardchirps"
    default_auto_field = "django.db.models.BigAutoField"
    # Pinned to the name the app had before the project was renamed. Django works the
    # label out from the package otherwise, and the label is what every migration and
    # every table name is built from, so letting it follow the rename would ask each
    # existing station to move its whole database for nothing. Only Django sees this.
    label = "birds_recorder"
