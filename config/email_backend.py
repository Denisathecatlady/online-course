"""
Vlastní SMTP backend který vynutí IPv4 připojení.

Render a některé další servery mají broken IPv6 routing →
OSError: [Errno 101] Network is unreachable při pokusu o IPv6.
Tento backend přepíše socket.getaddrinfo aby vrátil jen IPv4 adresy.
"""

import socket
from django.core.mail.backends.smtp import EmailBackend as _SMTPBackend


class IPv4EmailBackend(_SMTPBackend):
    """SMTP backend s vynuceným IPv4 – řeší ENETUNREACH na Render."""

    def open(self):
        _orig = socket.getaddrinfo

        def _ipv4_only(host, port, family=0, socktype=0, proto=0, flags=0):
            return _orig(host, port, socket.AF_INET, socktype, proto, flags)

        socket.getaddrinfo = _ipv4_only
        try:
            return super().open()
        finally:
            socket.getaddrinfo = _orig
