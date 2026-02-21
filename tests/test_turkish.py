"""Tests for suggestguard.analyzers.turkish module."""

from __future__ import annotations

import pytest

from suggestguard.analyzers.turkish import TurkishTextProcessor


@pytest.fixture
def tp() -> TurkishTextProcessor:
    return TurkishTextProcessor()


# ── normalize ────────────────────────────────────────────────────────


class TestNormalize:
    def test_whitespace_and_lower(self, tp: TurkishTextProcessor):
        assert tp.normalize("  ELMA  YAYINEVİ  ") == "elma yayınevi"

    def test_dotted_i_becomes_i(self, tp: TurkishTextProcessor):
        # İstanbul → istanbul (not ıstanbul)
        assert tp.normalize("İSTANBUL") == "istanbul"

    def test_undotted_i_becomes_ı(self, tp: TurkishTextProcessor):
        # ISIK → ısık (not isik)
        assert tp.normalize("IŞIK") == "ışık"

    def test_mixed_case(self, tp: TurkishTextProcessor):
        assert tp.normalize("Türkİye") == "türkiye"

    def test_already_lower(self, tp: TurkishTextProcessor):
        assert tp.normalize("merhaba dünya") == "merhaba dünya"

    def test_empty_string(self, tp: TurkishTextProcessor):
        assert tp.normalize("") == ""

    def test_tabs_and_newlines(self, tp: TurkishTextProcessor):
        assert tp.normalize("a\t\nb") == "a b"


# ── ascii_variants ───────────────────────────────────────────────────


class TestAsciiVariants:
    def test_all_special_chars(self, tp: TurkishTextProcessor):
        assert tp.ascii_variants("şçöüğı") == "scougi"

    def test_uppercase_specials(self, tp: TurkishTextProcessor):
        assert tp.ascii_variants("ŞÇÖÜĞ") == "SCOUG"

    def test_mixed_text(self, tp: TurkishTextProcessor):
        assert tp.ascii_variants("türkçe") == "turkce"

    def test_no_change(self, tp: TurkishTextProcessor):
        assert tp.ascii_variants("hello") == "hello"

    def test_empty_string(self, tp: TurkishTextProcessor):
        assert tp.ascii_variants("") == ""


# ── generate_query_variants ──────────────────────────────────────────


class TestGenerateQueryVariants:
    def test_base_only(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("Test", expand_az=False, expand_turkish=False)
        assert variants == ["test"]

    def test_ascii_variant_included(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("Türkçe", expand_az=False, expand_turkish=False)
        assert variants == ["türkçe", "turkce"]

    def test_no_duplicate_ascii(self, tp: TurkishTextProcessor):
        # "hello" has no Turkish chars → ascii == base → no duplicate
        variants = tp.generate_query_variants("hello", expand_az=False, expand_turkish=False)
        assert variants == ["hello"]

    def test_expand_az(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("marka", expand_az=True, expand_turkish=False)
        # base + 26 letters
        assert len(variants) == 27
        assert variants[0] == "marka"
        assert "marka a" in variants
        assert "marka z" in variants

    def test_expand_turkish(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("marka", expand_az=False, expand_turkish=True)
        # base + 6 Turkish chars
        assert len(variants) == 7
        assert "marka ş" in variants
        assert "marka ı" in variants

    def test_full_expansion(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("marka", expand_az=True, expand_turkish=True)
        # base(1) + az(26) + turkish(6) = 33
        assert len(variants) == 33

    def test_full_expansion_with_ascii_variant(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("şirket", expand_az=True, expand_turkish=True)
        # base(1) + ascii(1) + az(26) + turkish(6) = 34
        assert len(variants) == 34
        assert variants[0] == "şirket"
        assert variants[1] == "sirket"

    def test_deduplicated(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("abc", expand_az=True, expand_turkish=False)
        assert len(variants) == len(set(variants))

    def test_normalize_applied(self, tp: TurkishTextProcessor):
        variants = tp.generate_query_variants("  BİR  İKİ  ", expand_az=False, expand_turkish=False)
        assert variants[0] == "bir iki"


# ── detect_language ──────────────────────────────────────────────────


class TestDetectLanguage:
    def test_turkish_chars(self, tp: TurkishTextProcessor):
        assert tp.detect_language("şirket") == "tr"
        assert tp.detect_language("çay") == "tr"
        assert tp.detect_language("göl") == "tr"
        assert tp.detect_language("gül") == "tr"
        assert tp.detect_language("dağ") == "tr"
        assert tp.detect_language("sığır") == "tr"
        assert tp.detect_language("İstanbul") == "tr"

    def test_no_turkish(self, tp: TurkishTextProcessor):
        assert tp.detect_language("hello world") == "unknown"

    def test_empty_string(self, tp: TurkishTextProcessor):
        assert tp.detect_language("") == "unknown"

    def test_mixed_text(self, tp: TurkishTextProcessor):
        assert tp.detect_language("brand şikayet") == "tr"
