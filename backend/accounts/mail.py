import os
from django.core.mail.backends.filebased import EmailBackend
class PrivateFileBackend(EmailBackend):
    """Development messages contain live tokens: keep outside static paths."""
    def open(self):
        os.makedirs(self.file_path, mode=0o700, exist_ok=True)
        os.chmod(self.file_path, 0o700)
        opened = super().open()
        if self.stream:
            os.chmod(self.stream.name, 0o600)
        return opened
