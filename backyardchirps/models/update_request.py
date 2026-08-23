from django.db import models


class StoredUpdateRequest(models.Model):
    """
    The version an admin asked the station to install. One row, replaced each time.

    This is the only thing the web process tells the updater, and the updater treats it
    as a request rather than an instruction: it re-reads the manifest itself and refuses
    anything the manifest does not currently offer.
    """

    version = models.CharField(max_length=100)
    requested_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "update request"

    def __str__(self) -> str:
        return self.version
