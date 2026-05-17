import unittest
from unittest.mock import MagicMock, patch
import sys

# Define exception classes to be used in mocks
class MockBaseException(Exception):
    pass

class RateLimitError(MockBaseException):
    pass

class AuthenticationError(MockBaseException):
    pass

class PermissionDeniedError(MockBaseException):
    pass

class BadRequestError(MockBaseException):
    pass

class InternalServerError(MockBaseException):
    pass

class APIConnectionError(MockBaseException):
    pass

class APITimeoutError(MockBaseException):
    pass

class APIStatusError(MockBaseException):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

# Mock the openai module
mock_openai = MagicMock()
mock_openai.RateLimitError = RateLimitError
mock_openai.AuthenticationError = AuthenticationError
mock_openai.PermissionDeniedError = PermissionDeniedError
mock_openai.BadRequestError = BadRequestError
mock_openai.InternalServerError = InternalServerError
mock_openai.APIConnectionError = APIConnectionError
mock_openai.APITimeoutError = APITimeoutError
mock_openai.APIStatusError = APIStatusError

# Use a patch to mock 'openai' while importing the function under test.
# This prevents leaking the mock to other parts of the system if more tests are added.
with patch.dict(sys.modules, {'openai': mock_openai}):
    from utils.llm_errors import provider_error_reply

class TestLLMErrors(unittest.TestCase):
    def test_rate_limit_error(self):
        exc = RateLimitError("Rate limit exceeded")
        result = provider_error_reply(exc)
        self.assertIn("Groq rate or token limits", result)

    def test_authentication_error(self):
        exc = AuthenticationError("Invalid API key")
        result = provider_error_reply(exc)
        self.assertIn("Groq rejected your API key", result)

    def test_permission_denied_error(self):
        exc = PermissionDeniedError("Access denied")
        result = provider_error_reply(exc)
        self.assertIn("Groq denied this request", result)

    def test_bad_request_error_context(self):
        for msg in ["context window", "too long", "maximum token budget"]:
            with self.subTest(msg=msg):
                exc = BadRequestError(msg)
                result = provider_error_reply(exc)
                self.assertIn("too large for the model’s context window", result)

    def test_bad_request_error_model(self):
        for msg in ["model not found", "model does not exist", "invalid model"]:
            with self.subTest(msg=msg):
                exc = BadRequestError(msg)
                result = provider_error_reply(exc)
                self.assertIn("model name in GROQ_MODEL is not accepted", result)

    def test_bad_request_error_generic(self):
        exc = BadRequestError("some other error")
        result = provider_error_reply(exc)
        self.assertEqual(result, "Groq rejected the request: some other error")

    def test_internal_server_error(self):
        exc = InternalServerError("Server error")
        result = provider_error_reply(exc)
        self.assertIn("Groq returned a temporary server error", result)

    def test_network_errors(self):
        for exc_class in [APIConnectionError, APITimeoutError]:
            with self.subTest(exc_class=exc_class):
                exc = exc_class("Network issue")
                result = provider_error_reply(exc)
                self.assertIn("Could not reach Groq", result)

    def test_api_status_error_429(self):
        exc = APIStatusError("Too many requests", status_code=429)
        result = provider_error_reply(exc)
        self.assertIn("Groq rate or token limits", result)

    def test_api_status_error_generic(self):
        exc = APIStatusError("Internal Error", status_code=500)
        result = provider_error_reply(exc)
        self.assertEqual(result, "Groq returned HTTP 500. Details: Internal Error")

    def test_api_status_error_no_code(self):
        exc = APIStatusError("Some error")
        result = provider_error_reply(exc)
        self.assertEqual(result, "Groq API error: Some error")

    def test_api_status_error_no_code_no_body(self):
        exc = APIStatusError("")
        result = provider_error_reply(exc)
        self.assertEqual(result, "Groq API error: APIStatusError")

    def test_unknown_exception(self):
        exc = ValueError("Unknown error")
        result = provider_error_reply(exc)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
