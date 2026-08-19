import unittest
from unittest.mock import Mock, patch

import requests

from llm.qwen_client import LocalQwen, LocalQwenError


class LocalQwenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = LocalQwen()

    @patch("llm.qwen_client.requests.post")
    def test_returns_message_content(self, mocked_post: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {
                "content": '{"action":"unsupported","panel":null}',
            }
        }
        mocked_post.return_value = response

        result = self.client._call("prompt")

        self.assertIn("unsupported", result)

    @patch("llm.qwen_client.requests.post")
    def test_converts_timeout_to_retryable_error(
        self,
        mocked_post: Mock,
    ) -> None:
        mocked_post.side_effect = requests.Timeout("timeout")

        with self.assertRaises(LocalQwenError) as context:
            self.client._call("prompt")

        self.assertEqual(context.exception.error_code, "LLM_TIMEOUT")
        self.assertTrue(context.exception.retryable)

    @patch("llm.qwen_client.requests.post")
    def test_converts_connection_failure(self, mocked_post: Mock) -> None:
        mocked_post.side_effect = requests.ConnectionError("offline")

        with self.assertRaises(LocalQwenError) as context:
            self.client._call("prompt")

        self.assertEqual(context.exception.error_code, "LLM_UNAVAILABLE")

    @patch("llm.qwen_client.requests.post")
    def test_preserves_http_status_for_server_error(
        self,
        mocked_post: Mock,
    ) -> None:
        raw_response = requests.Response()
        raw_response.status_code = 503
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            response=raw_response,
        )
        mocked_post.return_value = response

        with self.assertRaises(LocalQwenError) as context:
            self.client._call("prompt")

        self.assertEqual(context.exception.error_code, "LLM_HTTP_ERROR")
        self.assertIn("503", str(context.exception))
        self.assertTrue(context.exception.retryable)

    @patch("llm.qwen_client.requests.post")
    def test_rejects_response_without_content(self, mocked_post: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"message": {}}
        mocked_post.return_value = response

        with self.assertRaises(LocalQwenError) as context:
            self.client._call("prompt")

        self.assertEqual(
            context.exception.error_code,
            "LLM_INVALID_RESPONSE",
        )


if __name__ == "__main__":
    unittest.main()
