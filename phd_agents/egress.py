from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.request import HTTPHandler, HTTPSHandler


class EgressDenied(OSError):
    pass


def permitted_addresses(host: str, port: int, *, local: bool) -> tuple[str, ...]:
    if not host or not 1 <= port <= 65535:
        raise EgressDenied("Invalid provider network destination")
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise EgressDenied("Provider DNS resolution failed") from error
    if not answers or len(answers) > 32:
        raise EgressDenied("Provider DNS returned no usable or too many addresses")
    selected: list[str] = []
    for family, kind, _, _, destination in answers:
        if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM:
            raise EgressDenied("Provider DNS returned an unsupported address family")
        literal = destination[0]
        try:
            address = ipaddress.ip_address(literal)
        except ValueError as error:
            raise EgressDenied("Provider DNS returned an invalid address") from error
        if address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not (address.is_loopback if local else address.is_global):
            raise EgressDenied("Provider DNS returned a forbidden network address")
        value = str(address)
        if value not in selected:
            selected.append(value)
    if not selected:
        raise EgressDenied("Provider DNS returned no permitted addresses")
    return tuple(selected)


def pinned_socket(host: str, port: int, *, local: bool, timeout: object,
                  source_address: tuple[str, int] | None = None) -> socket.socket:
    destinations = permitted_addresses(host, port, local=local)
    last_error: OSError | None = None
    for address in destinations:
        try:
            return socket.create_connection((address, port), timeout, source_address)
        except OSError as error:
            last_error = error
    raise EgressDenied("Unable to connect to a permitted provider address") from last_error


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, *args: object, local: bool = False, **kwargs: object):
        super().__init__(host, *args, **kwargs)
        self.local = local

    def connect(self) -> None:
        self.sock = pinned_socket(self.host, self.port, local=self.local,
                                  timeout=self.timeout, source_address=self.source_address)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *args: object, local: bool = False, **kwargs: object):
        super().__init__(host, *args, **kwargs)
        self.local = local

    def connect(self) -> None:
        raw = pinned_socket(self.host, self.port, local=self.local,
                            timeout=self.timeout, source_address=self.source_address)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except (OSError, ValueError):
            raw.close()
            raise


class PinnedHTTPHandler(HTTPHandler):
    def __init__(self, *, local: bool):
        super().__init__()
        self.local = local

    def http_open(self, request: object) -> object:
        return self.do_open(PinnedHTTPConnection, request, local=self.local)


class PinnedHTTPSHandler(HTTPSHandler):
    def __init__(self, *, local: bool):
        super().__init__(context=ssl.create_default_context())
        self.local = local

    def https_open(self, request: object) -> object:
        return self.do_open(PinnedHTTPSConnection, request, context=self._context,
                            local=self.local)
