from base64 import b64encode
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.errors import PalimpsestError
from palimpsest.local_glm_provider import LocalGLMProvider, MAX_OUTPUT_TOKENS, MODEL, PROFILE


class Reply:
    def __init__(self, value):
        self.value = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.value


class LocalGLMProviderTests(unittest.TestCase):
    def test_strict_schema_image_receipt_and_truncation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "page.png"
            image.write_bytes(b"synthetic-png")
            schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
                      "required": ["ok"], "additionalProperties": False}
            captured = []

            def answer(request, timeout):
                captured.append((json.loads(request.data), timeout))
                return Reply({"id": "chatcmpl-independent-1", "model": MODEL,
                    "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7,
                              "completion_tokens_details": {"reasoning_tokens": 3}}})

            with patch("palimpsest.local_glm_provider.urlopen", side_effect=answer):
                result = LocalGLMProvider(17).generate(prompt="Review", schema=schema, images=[image], cwd=root)
            payload, timeout = captured[0]
            self.assertEqual((result.output, result.thread_ref, timeout), ({"ok": True}, "chatcmpl-independent-1", 17))
            self.assertEqual(result.usage, {"input_tokens": 11, "output_tokens": 7, "reasoning_output_tokens": 3})
            self.assertEqual({key: result.profile[key] for key in PROFILE}, PROFILE)
            self.assertEqual(payload["response_format"]["json_schema"]["schema"], schema)
            self.assertEqual(payload["max_tokens"], MAX_OUTPUT_TOKENS)
            self.assertEqual(payload["messages"][1]["content"][1]["image_url"]["url"],
                             "data:image/png;base64," + b64encode(b"synthetic-png").decode())

            truncated = {"id": "chatcmpl-independent-2", "model": MODEL,
                         "choices": [{"finish_reason": "length", "message": {"content": None}}]}
            with patch("palimpsest.local_glm_provider.urlopen", return_value=Reply(truncated)), \
                    self.assertRaises(PalimpsestError) as raised:
                LocalGLMProvider().generate(prompt="Review", schema=schema, cwd=root)
            self.assertEqual(raised.exception.code, "local_glm_output_truncated")


if __name__ == "__main__":
    unittest.main()
