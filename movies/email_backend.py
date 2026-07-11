from django.core.mail.backends.smtp import EmailBackend
import smtplib

class PatchedEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False

        # Use a safe fallback check in case local_hostname doesn't exist on this Django version
        connection_params = {}
        local_hostname = getattr(self, 'local_hostname', None)
        if local_hostname:
            connection_params['local_hostname'] = local_hostname
            
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout

        try:
            # Open a secure connection directly over SSL on Port 465
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
