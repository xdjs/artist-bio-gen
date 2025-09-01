#!/usr/bin/env python3
"""
Unit tests for text cleaning utilities.

These tests focus on stripping trailing citation/link blocks from
OpenAI responses while preserving legitimate content.
"""

import unittest


class TestStripTrailingCitations(unittest.TestCase):
    def setUp(self):
        # Import here to avoid import errors before implementation
        from artist_bio_gen.utils.text import strip_trailing_citations  # type: ignore

        self.strip_trailing_citations = strip_trailing_citations

    def test_strip_parenthetical_links_block(self):
        text = (
            "03 Greedo, the Watts-born crooner-rapper, is riding a blistering 2025 with a "
            "flood of new music on SoundCloud—including Nothing Else To Do, Kicc Stand, and "
            "Killa 2 Yo Killa posted July 15, 2025—alongside earlier 2025 drops like Take Me "
            "Somewhere, Take My Hand, Crushing On Twin, Boujee, and My Baby (feat. Shordie Shordie). "
            "His sprawling 21‑song project 2025: THE STREETZ IS OVER WIIT pulls in a who’s-who of "
            "producers (RonRontheProducer, Turbo) and guests (Babyfxce E, DC2Trill, RX Peso). Live "
            "updates include a DTLA show with OHGEESY on May 23, 2025. It all sits atop a melodic, "
            "Auto-Tuned West Coast vibe he’s famous for—think Purple Summer/Wolf of Grape Street energy, "
            "now amplified under Golden Grenade Empire. ([soundcloud.com](https://soundcloud.com/03greedo?utm_source=openai), "
            "[vuulm.com](https://www.vuulm.com/albums/03-greedo-2025-the-streetz-is-over-wiit?utm_source=openai), "
            "[catwalk.uvtix.com](https://catwalk.uvtix.com/event/uv7012606672dt250523/underground-presents-oghessy-and-03greedo/?utm_source=openai), "
            "[en.wikipedia.org](https://en.wikipedia.org/wiki/03_Greedo?utm_source=openai), "
            "[stereogum.com](https://www.stereogum.com/2288377/03-greedo-hella-greedy-crip-im-sexy/interviews/qa/?utm_source=openai))"
        )
        expected = (
            "03 Greedo, the Watts-born crooner-rapper, is riding a blistering 2025 with a "
            "flood of new music on SoundCloud—including Nothing Else To Do, Kicc Stand, and "
            "Killa 2 Yo Killa posted July 15, 2025—alongside earlier 2025 drops like Take Me "
            "Somewhere, Take My Hand, Crushing On Twin, Boujee, and My Baby (feat. Shordie Shordie). "
            "His sprawling 21‑song project 2025: THE STREETZ IS OVER WIIT pulls in a who’s-who of "
            "producers (RonRontheProducer, Turbo) and guests (Babyfxce E, DC2Trill, RX Peso). Live "
            "updates include a DTLA show with OHGEESY on May 23, 2025. It all sits atop a melodic, "
            "Auto-Tuned West Coast vibe he’s famous for—think Purple Summer/Wolf of Grape Street energy, "
            "now amplified under Golden Grenade Empire."
        )

        cleaned = self.strip_trailing_citations(text)
        self.assertEqual(cleaned, expected)

    def test_preserve_mid_text_links(self):
        text = (
            "He cited [Wikipedia](https://en.wikipedia.org/wiki/Artist) for background, which was notable."
        )
        cleaned = self.strip_trailing_citations(text)
        self.assertEqual(cleaned, text)

    def test_strip_sources_line(self):
        text = (
            "A concise bio ending with references.\n"
            "Sources: [site A](https://a.test), [site B](https://b.test)\n"
        )
        expected = "A concise bio ending with references."
        cleaned = self.strip_trailing_citations(text)
        self.assertEqual(cleaned, expected)

    def test_keep_parentheses_without_links(self):
        text = "An artist born (1990) in LA."
        cleaned = self.strip_trailing_citations(text)
        self.assertEqual(cleaned, text)

    def test_idempotent(self):
        text = "Sentence. ( [Link](https://example.com), https://x.test )"
        once = self.strip_trailing_citations(text)
        twice = self.strip_trailing_citations(once)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()

