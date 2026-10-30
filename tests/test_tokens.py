"""The estimator: deterministic, CJK-aware, honest about emptiness."""

from ctxlens import tokens as tok


def test_ascii_divides_by_four():
    assert tok.estimate_tokens("abcd" * 4) == 4
    assert tok.estimate_tokens("hello world!") == 3  # 12 chars -> 3


def test_cjk_is_one_token_per_char():
    assert tok.estimate_tokens("上下文窗口") == 5
    assert tok.estimate_tokens("こんにちは世界") == 7
    assert tok.estimate_tokens("안녕하세요") == 5


def test_mixed_text():
    # 8 ascii chars -> 2, plus 4 cjk -> 4  => 6
    assert tok.estimate_tokens("test测试abcd中文") == 6


def test_empty_and_whitespace_are_zero():
    assert tok.estimate_tokens("") == 0
    assert tok.estimate_tokens("   \n\t  ") == 0


def test_single_char_still_counts():
    assert tok.estimate_tokens("a") == 1
    assert tok.estimate_tokens("中") == 1


def test_deterministic_across_runs():
    sample = "payments/processor.py 双扣费 bug, retry window 1900 lines"
    first = tok.estimate_tokens(sample)
    for _ in range(5):
        assert tok.estimate_tokens(sample) == first


def test_estimate_object_is_stable_and_sorted():
    obj = {"b": 1, "a": "x"}
    assert tok.estimate_object(obj) == tok.estimate_object({"a": "x", "b": 1})
    assert tok.estimate_object(None) == 0


def test_estimate_object_handles_unserializable():
    class Weird:
        def __str__(self):
            return "weird-object"

    assert tok.estimate_object(Weird()) > 0
