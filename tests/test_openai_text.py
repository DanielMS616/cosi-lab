"""Check the adapter offline by replacing only its HTTPS connection boundary."""

import copy
import http.client
import io
import json
import os
import ssl
import traceback
import unittest
from unittest.mock import patch

from openai_text import OpenAITextError, generate_text


class FakeHTTPResponse(io.BytesIO):
    """Supply an HTTP status and readable bytes with normal context-manager closing."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        super().__init__(body)
        self.status = status


class OpenAITextTests(unittest.TestCase):
    """Exercise real request construction and parsing without contacting a model."""

    def setUp(self) -> None:
        """Isolate environment settings and prevent every real HTTPS connection."""
        environment = patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        boundary = patch("openai_text.http.client.HTTPSConnection")
        self.connection_factory = boundary.start()
        self.addCleanup(boundary.stop)
        self.connection = self.connection_factory.return_value
        self.completed_response = {
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "output": [{
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Temperatur: 53,6 °C."}],
            }],
        }

    def provide_response(self, payload: object, status: int = 200) -> FakeHTTPResponse:
        """Encode a fixture as real JSON bytes at the HTTP response boundary."""
        response = FakeHTTPResponse(json.dumps(payload).encode("utf-8"), status)
        self.connection.getresponse.return_value = response
        return response

    def assert_single_request_closed(self) -> None:
        """A completed attempt must not retry and must release the connection."""
        self.connection_factory.assert_called_once()
        self.connection.request.assert_called_once()
        self.connection.close.assert_called_once()

    def assert_diagnosis(self, error: OpenAITextError, code: str, status: int | None = 200) -> None:
        """Check stable metadata separately from the existing readable error message."""
        self.assertEqual(error.error_code, code)
        self.assertEqual(error.http_status, status)

    def test_legacy_exception_call_and_fixed_diagnostic_values(self) -> None:
        """Old construction retains its message; arbitrary code text is not accepted."""
        error = OpenAITextError("Fehlermeldung")
        self.assertEqual(str(error), "Fehlermeldung")
        self.assertEqual(error.args, ("Fehlermeldung",))
        self.assert_diagnosis(error, "unknown", None)
        error = OpenAITextError("Fehlermeldung", error_code="private-code-marker",
                                http_status="private-status-marker")
        self.assert_diagnosis(error, "unknown", None)

    def test_default_request_and_completed_text(self) -> None:
        """Check endpoint, credentials, JSON options, timeout, TLS, and cleanup."""
        response = self.provide_response(self.completed_response)

        result = generate_text("Erkläre die Temperatur in °C.")

        self.assertEqual(result, "Temperatur: 53,6 °C.")
        self.assert_single_request_closed()
        self.connection.getresponse.assert_called_once()
        self.assertTrue(response.closed)
        args, options = self.connection_factory.call_args
        self.assertEqual(args, ("api.openai.com",))
        self.assertEqual(options["timeout"], 30)
        self.assertEqual(options["context"].verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(options["context"].check_hostname)
        args, options = self.connection.request.call_args
        self.assertEqual(args, ("POST", "/v1/responses"))
        self.assertEqual(options["headers"]["Authorization"], "Bearer test-only-key")
        self.assertEqual(options["headers"]["Content-Type"], "application/json")
        self.assertEqual(json.loads(options["body"]), {
            "model": "gpt-4.1-mini",
            "input": "Erkläre die Temperatur in °C.",
            "max_output_tokens": 600,
            "store": False,
        })

    def test_model_is_configurable(self) -> None:
        """Forward the caller's model name without changing the request count."""
        self.provide_response(self.completed_response)
        generate_text("Bericht", model="test-model")
        payload = json.loads(self.connection.request.call_args.kwargs["body"])
        self.assertEqual(payload["model"], "test-model")
        self.assert_single_request_closed()

    def test_reads_key_on_each_call(self) -> None:
        """Environment changes after import take effect on the next invocation."""
        for key in ("first-test-key", "second-test-key"):
            with self.subTest(key=key):
                os.environ["OPENAI_API_KEY"] = key
                self.provide_response(self.completed_response)
                generate_text("Bericht")
                headers = self.connection.request.call_args.kwargs["headers"]
                self.assertEqual(headers["Authorization"], f"Bearer {key}")
        self.assertEqual(self.connection.request.call_count, 2)

    def test_missing_blank_or_invalid_key_prevents_http(self) -> None:
        """Missing credentials and invalid header characters fail locally."""
        for key in (None, "", " \t", "test\nkey", "test key", "täst"):
            with self.subTest(key=key):
                if key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = key
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht")
                self.assert_diagnosis(caught.exception, "configuration_error", None)
                self.connection_factory.assert_not_called()

    def test_invalid_prompt_or_model_prevents_http(self) -> None:
        """Type annotations do not replace validation at the public boundary."""
        for value in (None, 42, "", " \n"):
            with self.subTest(value=value):
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text(value)
                self.assert_diagnosis(caught.exception, "invalid_input", None)
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht", model=value)
                self.assert_diagnosis(caught.exception, "invalid_input", None)
                self.connection_factory.assert_not_called()

    def test_collects_text_after_other_outputs_in_order(self) -> None:
        """Reasoning may precede multiple text parts and messages."""
        payload = copy.deepcopy(self.completed_response)
        payload["output"].insert(0, {"type": "reasoning", "summary": []})
        payload["output"][1]["content"] = [
            {"type": "output_text", "text": "  Erstens: "},
            {"type": "output_text", "text": "53,6 °C.\n"},
        ]
        payload["output"].append({
            "type": "message", "status": "completed", "role": "assistant",
            "content": [{"type": "output_text", "text": "Zweitens.  "}],
        })
        self.provide_response(payload)
        self.assertEqual(generate_text("Bericht"), "  Erstens: 53,6 °C.\nZweitens.  ")
        self.assert_single_request_closed()

    def test_refusal_alone_raises_safe_error(self) -> None:
        """An explicit refusal has its own error without exposing its original text."""
        payload = copy.deepcopy(self.completed_response)
        payload["output"][0]["content"] = [
            {"type": "refusal", "refusal": "private-refusal-marker"},
        ]
        response = self.provide_response(payload)

        with self.assertRaisesRegex(OpenAITextError, "Auftrags abgelehnt") as caught:
            generate_text("Bericht")

        self.assertNotIn("private-refusal-marker", str(caught.exception))
        self.assert_diagnosis(caught.exception, "refusal")
        self.assert_single_request_closed()
        self.connection.getresponse.assert_called_once()
        self.assertTrue(response.closed)

    def test_refusal_with_text_always_raises_safe_error(self) -> None:
        """Text before or after a refusal, even in another message, cannot succeed."""
        text = {"type": "output_text", "text": "Gültiger Text."}
        refusal = {"type": "refusal", "refusal": "private-refusal-marker"}
        message_contents = (
            [[refusal, text]],
            [[text, refusal]],
            [[text, refusal, text]],
            [[text], [refusal]],
            [[refusal], [text]],
        )
        for contents in message_contents:
            with self.subTest(contents=contents):
                self.connection_factory.reset_mock()
                payload = copy.deepcopy(self.completed_response)
                payload["output"] = [
                    {"type": "message", "status": "completed",
                     "role": "assistant", "content": content}
                    for content in contents
                ]
                response = self.provide_response(payload)

                with self.assertRaisesRegex(OpenAITextError, "Auftrags abgelehnt") as caught:
                    generate_text("Bericht")

                self.assertNotIn("private-refusal-marker", str(caught.exception))
                self.assert_diagnosis(caught.exception, "refusal")
                self.assert_single_request_closed()
                self.connection.getresponse.assert_called_once()
                self.assertTrue(response.closed)

    def test_http_errors_and_redirects_are_not_retried_or_followed(self) -> None:
        """Even rate limits and redirect statuses cause just one failed attempt."""
        for status in (301, 302, 303, 307, 308, 400, 401, 429, 500, 503):
            with self.subTest(status=status):
                self.connection_factory.reset_mock()
                response = self.provide_response({"error": "private-server-marker"}, status)
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht")
                self.assertIn(str(status), str(caught.exception))
                self.assert_diagnosis(caught.exception, "http_error", status)
                self.assertNotIn("private-server-marker", str(caught.exception))
                self.assertNotIn("test-only-key", str(caught.exception))
                self.assert_single_request_closed()
                self.assertTrue(response.closed)

    def test_timeouts_during_request_and_response_are_not_retried(self) -> None:
        """Simulate socket timeouts at the HTTP boundary, not with real waiting."""
        for operation in ("request", "getresponse"):
            with self.subTest(operation=operation):
                self.connection_factory.reset_mock(side_effect=True)
                getattr(self.connection, operation).side_effect = TimeoutError("private-marker")
                with self.assertRaisesRegex(OpenAITextError, "Zeitüberschreitung") as caught:
                    generate_text("Bericht")
                self.assert_diagnosis(caught.exception, "timeout", None)
                self.assert_single_request_closed()

    def test_timeout_while_reading_closes_response_and_connection(self) -> None:
        """A stalled response body is also an error, with both resources closed."""
        response = self.provide_response(self.completed_response)
        # This replaces only reading from the fake HTTP response, not JSON parsing.
        with patch.object(response, "read", side_effect=TimeoutError("private-marker")):
            with self.assertRaisesRegex(OpenAITextError, "Zeitüberschreitung") as caught:
                generate_text("Bericht")
        self.assert_diagnosis(caught.exception, "timeout")
        self.assertTrue(response.closed)
        self.assert_single_request_closed()

    def test_network_and_protocol_errors_have_safe_messages(self) -> None:
        """Original network error messages must not leak through exception chains."""
        errors = (
            OSError("private-marker test-only-key Authorization"),
            ssl.SSLCertVerificationError("private-marker"),
            http.client.IncompleteRead(b"private-marker"),
        )
        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                self.connection_factory.reset_mock(side_effect=True)
                self.connection.request.side_effect = error
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht")
                rendered = "".join(traceback.format_exception(caught.exception))
                self.assert_diagnosis(caught.exception, "connection_error", None)
                for marker in ("private-marker", "test-only-key", "Authorization"):
                    self.assertNotIn(marker, rendered)
                self.assert_single_request_closed()

    def test_invalid_json_and_utf8_are_rejected(self) -> None:
        """Malformed JSON and Python-only numeric constants are not API success."""
        for body in (b"", b"not-json private-marker", b"{", b"\xff", b'{"x": NaN}'):
            with self.subTest(body=body):
                self.connection_factory.reset_mock()
                response = FakeHTTPResponse(body, status=201)
                self.connection.getresponse.return_value = response
                with self.assertRaisesRegex(OpenAITextError, "JSON") as caught:
                    generate_text("Bericht")
                self.assertNotIn("private-marker", str(caught.exception))
                self.assert_diagnosis(caught.exception, "invalid_json", 201)
                self.assert_single_request_closed()
                self.assertTrue(response.closed)

    def test_only_completed_status_succeeds(self) -> None:
        """Partial text is not usable when the response is incomplete or pending."""
        for status in (None, "incomplete", "failed", "cancelled", "queued", "in_progress"):
            with self.subTest(status=status):
                payload = copy.deepcopy(self.completed_response)
                payload["status"] = status
                self.provide_response(payload)
                with self.assertRaisesRegex(OpenAITextError, "abgeschlossen") as caught:
                    generate_text("Bericht")
                self.assert_diagnosis(caught.exception, "incomplete_response")

    def test_error_and_truncation_details_are_rejected(self) -> None:
        """Even contradictory completed responses cannot hide truncation or errors."""
        for field, value in (
            ("incomplete_details", {"reason": "max_output_tokens"}),
            ("error", {"message": "private-server-marker"}),
        ):
            with self.subTest(field=field):
                payload = copy.deepcopy(self.completed_response)
                payload[field] = value
                self.provide_response(payload)
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht")
                self.assertNotIn("private-server-marker", str(caught.exception))
                expected_code = "incomplete_response" if field == "incomplete_details" else "invalid_response"
                self.assert_diagnosis(caught.exception, expected_code)

    def test_missing_or_blank_text_is_rejected(self) -> None:
        """No top-level shortcut can substitute for nonblank output text."""
        for content in ([],
                        [{"type": "output_text", "text": ""}],
                        [{"type": "output_text", "text": " \n\t"}]):
            with self.subTest(content=content):
                payload = copy.deepcopy(self.completed_response)
                payload["output"][0]["content"] = content
                payload["output_text"] = "Do not use this shortcut."
                self.provide_response(payload)
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht")
                self.assert_diagnosis(caught.exception, "empty_response")

    def test_malformed_response_shapes_are_rejected(self) -> None:
        """Malformed objects fail with the adapter's error rather than TypeError."""
        invalid_payloads = [(None, "invalid_response"), ([], "invalid_response"),
                            ("text", "invalid_response"), ({}, "incomplete_response"),
                            ({"status": "completed"}, "invalid_response")]
        for output, expected_code in ((None, "invalid_response"), ({}, "invalid_response"),
                       ([], "empty_response"), ([None], "invalid_response"),
                       ([{"type": "message", "content": None}], "invalid_response"),
                       ([{"type": "message", "content": [None]}], "invalid_response"),
                       ([{"type": "message", "content": [{"type": "output_text", "text": 7}]}], "invalid_response"),
                       ([{"type": "message", "status": "incomplete", "content": []}], "incomplete_response")):
            invalid_payloads.append(({"status": "completed", "output": output}, expected_code))
        for payload, expected_code in invalid_payloads:
            with self.subTest(payload=payload):
                self.provide_response(payload)
                with self.assertRaises(OpenAITextError) as caught:
                    generate_text("Bericht")
                self.assert_diagnosis(caught.exception, expected_code)


if __name__ == "__main__":
    unittest.main()
