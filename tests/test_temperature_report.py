"""Check the text boundary offline; fixed answers do not measure model quality."""

import copy
import json
import unittest

from temperature_report import generate_temperature_report


FIXED_RESPONSE = (
    "Von 6 Messwerten sind 5 gültig und einer fehlt. Die gültigen Temperaturen "
    "liegen zwischen 40 und 65 °C, ihr Mittelwert beträgt 53,6 °C. "
    "Zwei Werte liegen strikt oberhalb von 60 °C. Ursachen sind daraus nicht ableitbar."
)


class TemperatureReportTests(unittest.TestCase):
    """Record generator requests and check facts, calls, responses, and errors."""

    def setUp(self) -> None:
        """Use the existing analysis contract without calculating statistics again."""
        self.analysis_result = {
            "total_count": 6,
            "valid_count": 5,
            "missing_count": 1,
            "minimum": 40,
            "maximum": 65,
            "mean": 53.6,
            "exceedance_count": 2,
        }

    def test_passes_facts_once_and_returns_fixed_response(self) -> None:
        """The generator receives exactly the agreed facts in one text request."""
        received_prompts: list[str] = []

        def generator(prompt: str) -> str:
            """Capture the request and return a fixed answer without a model."""
            received_prompts.append(prompt)
            return FIXED_RESPONSE

        response = generate_temperature_report(self.analysis_result, 60, generator)

        self.assertEqual(response, FIXED_RESPONSE)
        self.assertEqual(len(received_prompts), 1)
        prompt = received_prompts[0]
        self.assertIsInstance(prompt, str)
        facts = json.loads(prompt.split("Kennzahlen (JSON):\n", 1)[1])
        self.assertEqual(facts, {**self.analysis_result, "threshold": 60})
        self.assertIn("kurzen deutschen Temperaturbericht", prompt)
        self.assertIn("fehlende Messwerte", prompt)
        self.assertIn("nicht ersetzt", prompt)
        self.assertIn("strikt größer als threshold", prompt)
        self.assertIn("Schwellenwert zählen nicht als Überschreitung", prompt)
        self.assertIn("Erfinde keine Ursachen", prompt)
        self.assertIn("°C", prompt)

    def test_extra_input_contents_are_not_forwarded_or_modified(self) -> None:
        """Even unexpected metadata cannot leak through the numeric allowlist."""
        analysis = dict(self.analysis_result)
        analysis["csv_raw_data"] = "private-raw-data-marker"
        analysis["path"] = "/private/input-marker.csv"
        original = copy.deepcopy(analysis)
        received_prompts: list[str] = []

        def generator(prompt: str) -> str:
            """Record only the text supplied by the report boundary."""
            received_prompts.append(prompt)
            return FIXED_RESPONSE

        generate_temperature_report(analysis, 60, generator)

        self.assertEqual(len(received_prompts), 1)
        prompt = received_prompts[0]
        facts = json.loads(prompt.split("Kennzahlen (JSON):\n", 1)[1])
        self.assertEqual(facts, {**self.analysis_result, "threshold": 60})
        self.assertNotIn("private-raw-data-marker", prompt)
        self.assertNotIn("/private/input-marker.csv", prompt)
        self.assertEqual(analysis, original)

    def test_preserves_numeric_precision_and_custom_threshold(self) -> None:
        """Copy supplied statistics without deriving or rounding new values."""
        analysis = dict(self.analysis_result)
        analysis["mean"] = 53.6123456789
        analysis["exceedance_count"] = 0
        received_prompts: list[str] = []

        def generator(prompt: str) -> str:
            """Return a fixed answer; its contents are outside this test's scope."""
            received_prompts.append(prompt)
            return "Feste Testantwort."

        generate_temperature_report(analysis, 65.5, generator)

        self.assertEqual(len(received_prompts), 1)
        facts = json.loads(received_prompts[0].split("Kennzahlen (JSON):\n", 1)[1])
        self.assertEqual(facts, {**analysis, "threshold": 65.5})

    def test_nonblank_response_is_returned_unchanged(self) -> None:
        """Whitespace around valid text is not removed or otherwise rewritten."""
        received_prompts: list[str] = []
        expected = "  Feste Testantwort.\n"

        def generator(prompt: str) -> str:
            """Capture the call and return deliberately padded text."""
            received_prompts.append(prompt)
            return expected

        response = generate_temperature_report(self.analysis_result, 60, generator)

        self.assertEqual(response, expected)
        self.assertEqual(len(received_prompts), 1)

    def test_invalid_responses_raise_value_error_without_retry(self) -> None:
        """Reject non-text, empty text, and whitespace-only text after one call."""
        invalid_responses = [None, 42, True, b"text", [], {}, "", "   ", "\n\t", "\u2003"]
        for answer in invalid_responses:
            with self.subTest(answer=answer):
                received_prompts: list[str] = []

                def generator(prompt: str) -> object:
                    """Intentionally violate the promised text-return contract."""
                    received_prompts.append(prompt)
                    return answer

                with self.assertRaises(ValueError):
                    generate_temperature_report(self.analysis_result, 60, generator)
                self.assertEqual(len(received_prompts), 1)

    def test_generator_exceptions_propagate_unchanged_without_retry(self) -> None:
        """Preserve the exact exception object instead of wrapping or hiding it."""
        for error in (RuntimeError("failed"), OSError("failed"), ValueError("failed")):
            with self.subTest(error_type=type(error).__name__):
                received_prompts: list[str] = []

                def generator(prompt: str) -> str:
                    """Simulate failure at the external text-generation boundary."""
                    received_prompts.append(prompt)
                    raise error

                with self.assertRaises(type(error)) as caught:
                    generate_temperature_report(self.analysis_result, 60, generator)
                self.assertIs(caught.exception, error)
                self.assertEqual(len(received_prompts), 1)

    def test_missing_or_invalid_facts_do_not_reach_generator(self) -> None:
        """Reject text in numeric fields rather than including it in the request."""
        invalid_results = [None]
        missing_mean = dict(self.analysis_result)
        del missing_mean["mean"]
        invalid_results.append(missing_mean)
        for value in ("/private/input.csv", None, True, float("nan"), float("inf")):
            analysis = dict(self.analysis_result)
            analysis["mean"] = value
            invalid_results.append(analysis)

        for analysis in invalid_results:
            with self.subTest(analysis=analysis):
                received_prompts: list[str] = []

                def generator(prompt: str) -> str:
                    """Capture unexpected calls made with invalid input."""
                    received_prompts.append(prompt)
                    return FIXED_RESPONSE

                with self.assertRaises(ValueError):
                    generate_temperature_report(analysis, 60, generator)
                self.assertEqual(received_prompts, [])

    def test_invalid_threshold_does_not_reach_generator(self) -> None:
        """Only a finite numeric threshold can become a report fact."""
        for threshold in (None, "60", False, float("nan"), float("inf"), float("-inf")):
            with self.subTest(threshold=threshold):
                received_prompts: list[str] = []

                def generator(prompt: str) -> str:
                    """Capture unexpected calls made with an invalid threshold."""
                    received_prompts.append(prompt)
                    return FIXED_RESPONSE

                with self.assertRaises(ValueError):
                    generate_temperature_report(self.analysis_result, threshold, generator)
                self.assertEqual(received_prompts, [])
