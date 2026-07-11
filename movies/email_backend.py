from django.core.mail.backends.smtp import EmailBackend
import smtplib
import ssl

class PatchedEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False

        connection_params = {'local_hostname': self.local_hostname}
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout

        try:
            # Force standard SMTP initialization safely
            self.connection = smtplib.SMTP_SSL(
                self.host, 
                self.port, 
                **connection_params
            )
            
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except Exception:
            if not self.fail_silently:
                raise
            return False
