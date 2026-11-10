from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

from phd_agents.connectivity import model_list
from phd_agents.egress import EgressDenied, PinnedHTTPSConnection, permitted_addresses, pinned_socket
from phd_agents.providers import invoke


def record(ip: str, port: int = 443) -> tuple:
    family = socket.AF_INET6 if ipaddress.ip_address(ip).version == 6 else socket.AF_INET
    destination = (ip, port, 0, 0) if family == socket.AF_INET6 else (ip, port)
    return (family, socket.SOCK_STREAM, 6, "", destination)


class EgressValidationTests(unittest.TestCase):
    def test_global_cloud_addresses_only(self) -> None:
        with patch("phd_agents.egress.socket.getaddrinfo", return_value=[record("1.1.1.1"), record("2606:4700:4700::1111")]):
            self.assertEqual(permitted_addresses("api.example", 443, local=False), ("1.1.1.1", "2606:4700:4700::1111"))
        for address in ("127.0.0.1", "10.0.0.1", "192.168.1.4", "169.254.169.254", "172.17.0.1", "::1", "fc00::1", "fe80::1"):
            with self.subTest(address=address), patch("phd_agents.egress.socket.getaddrinfo", return_value=[record(address)]):
                with self.assertRaises(EgressDenied):
                    permitted_addresses("malicious.example", 443, local=False)

    def test_mixed_public_private_dns_fails_closed(self) -> None:
        with patch("phd_agents.egress.socket.getaddrinfo", return_value=[record("1.1.1.1"), record("10.0.0.2")]):
            with self.assertRaises(EgressDenied):
                permitted_addresses("rebind.example", 443, local=False)

    def test_local_targets_never_resolve_off_host(self) -> None:
        with patch("phd_agents.egress.socket.getaddrinfo", return_value=[record("127.0.0.1")]):
            self.assertEqual(permitted_addresses("localhost", 443, local=True), ("127.0.0.1",))
        with patch("phd_agents.egress.socket.getaddrinfo", return_value=[record("1.1.1.1")]):
            with self.assertRaises(EgressDenied):
                permitted_addresses("localhost", 443, local=True)

    def test_connect_uses_verified_literal_without_second_hostname_lookup(self) -> None:
        raw = Mock()
        with patch("phd_agents.egress.socket.getaddrinfo", return_value=[record("1.1.1.1")]) as dns:
            with patch("phd_agents.egress.socket.create_connection", return_value=raw) as connect:
                self.assertIs(pinned_socket("api.example", 443, local=False, timeout=3), raw)
        dns.assert_called_once()
        self.assertEqual(connect.call_args.args[0], ("1.1.1.1", 443))

    def test_tls_uses_original_name_for_certificate_validation(self) -> None:
        raw = Mock()
        context = Mock()
        wrapped = Mock()
        context.wrap_socket.return_value = wrapped
        conn = PinnedHTTPSConnection("api.example", 443, timeout=3)
        conn._context = context
        with patch("phd_agents.egress.pinned_socket", return_value=raw) as dial:
            conn.connect()
        self.assertIs(conn.sock, wrapped)
        self.assertEqual(dial.call_args.kwargs["local"], False)
        context.wrap_socket.assert_called_once_with(raw, server_hostname="api.example")


class LocalProviderTransportTests(unittest.TestCase):
    def test_inference_and_discovery_bypass_environment_proxy(self) -> None:
        class ModelServer(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                return

            def do_GET(self) -> None:
                payload = json.dumps({"data": [{"id": "test-local"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self) -> None:
                data = json.dumps({"choices": [{"message": {"content": "Source unverified"}}], "usage": {"prompt_tokens": 3}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), ModelServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        provider = {
            "id": "local_test", "local": True, "kind": "openai_compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1", "model": "test-local",
            "api_key_env": "", "max_output_tokens": 40, "token_parameter": "max_tokens",
        }
        try:
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1"}):
                self.assertEqual(model_list(provider)["models"][0]["id"], "test-local")
                self.assertEqual(invoke(provider, "System", "Prompt").content, "Source unverified")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
