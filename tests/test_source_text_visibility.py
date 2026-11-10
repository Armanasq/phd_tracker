from __future__ import annotations

import hashlib
import unittest

from phd_agents.source_text import EXCERPT_LIMIT, extract_visible_text


class SourceTextVisibilityTests(unittest.TestCase):
    def extract(self, html: str) -> dict:
        return extract_visible_text(html.encode("utf-8"), "text/html")

    def test_head_and_hidden_subtrees_do_not_create_false_admission_claims(self) -> None:
        text = self.extract('<html><head><title>Deadline 2099</title><style>.a{color:red}</style></head><body><p>Deadline 2026</p><div hidden><div><p>Fake deadline 2050</p></div><p>Also hidden</p></div><p>Apply now</p></body></html>')
        self.assertEqual(text["visible_text_excerpt"], "Deadline 2026 Apply now")

    def test_aria_and_inline_style_hidden_states(self) -> None:
        text = self.extract('<p aria-hidden="true">Stale date</p><p style="display: none">Wrong date</p><p style="visibility:hidden!important">Private draft</p><p>Verified visible text</p>')
        self.assertEqual(text["visible_text_excerpt"], "Verified visible text")

    def test_nested_same_tag_hidden_blocks_until_matching_close(self) -> None:
        text = self.extract('<div hidden><div>Secret</div><div>Also secret</div></div><div>Public</div>')
        self.assertEqual(text["visible_text_excerpt"], "Public")

    def test_void_tags_and_visible_text_are_preserved(self) -> None:
        text = self.extract('<p>Apply<br>by <input hidden> December 1</p>')
        self.assertEqual(text["visible_text_excerpt"], "Apply by December 1")

    def test_plain_text_hash_limit_and_normalization_are_unchanged(self) -> None:
        body = "A" * (EXCERPT_LIMIT + 5)
        text = extract_visible_text(body.encode("utf-8"), "text/plain")
        self.assertEqual(text["visible_text_length"], EXCERPT_LIMIT + 5)
        self.assertTrue(text["visible_text_truncated"])
        self.assertEqual(text["visible_text_sha256"], hashlib.sha256(body.encode()).hexdigest())

    def test_disallowed_media_and_oversized_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            extract_visible_text(b"abc", "application/pdf")
        with self.assertRaises(ValueError):
            extract_visible_text(b"x" * 2_000_001, "text/html")


if __name__ == "__main__":
    unittest.main()
