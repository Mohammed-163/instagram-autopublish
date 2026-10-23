"""
Unit tests for individual Hook Feature Analyzer plugins
(engines/hook_feature_analyzers/plugins).
"""
from __future__ import annotations

from engines.hook_feature_analyzers.plugins.average_word_length_analyzer import AverageWordLengthAnalyzer
from engines.hook_feature_analyzers.plugins.character_count_analyzer import CharacterCountAnalyzer
from engines.hook_feature_analyzers.plugins.colon_usage_analyzer import ColonUsageAnalyzer
from engines.hook_feature_analyzers.plugins.comparison_analyzer import ComparisonAnalyzer
from engines.hook_feature_analyzers.plugins.curiosity_analyzer import CuriosityAnalyzer
from engines.hook_feature_analyzers.plugins.emoji_analyzer import EmojiAnalyzer
from engines.hook_feature_analyzers.plugins.negation_analyzer import NegationAnalyzer
from engines.hook_feature_analyzers.plugins.number_analyzer import NumberAnalyzer
from engines.hook_feature_analyzers.plugins.opening_word_analyzer import OpeningWordAnalyzer
from engines.hook_feature_analyzers.plugins.parentheses_analyzer import ParenthesesAnalyzer
from engines.hook_feature_analyzers.plugins.percentage_analyzer import PercentageAnalyzer
from engines.hook_feature_analyzers.plugins.punctuation_analyzer import PunctuationAnalyzer
from engines.hook_feature_analyzers.plugins.question_analyzer import QuestionAnalyzer
from engines.hook_feature_analyzers.plugins.quotation_marks_analyzer import QuotationMarksAnalyzer
from engines.hook_feature_analyzers.plugins.sentence_length_analyzer import SentenceLengthAnalyzer
from engines.hook_feature_analyzers.plugins.uppercase_ratio_analyzer import UppercaseRatioAnalyzer
from engines.hook_feature_analyzers.plugins.warning_analyzer import WarningAnalyzer
from engines.hook_feature_analyzers.plugins.whitespace_pattern_analyzer import WhitespacePatternAnalyzer
from engines.hook_feature_analyzers.plugins.word_count_analyzer import WordCountAnalyzer


def test_number_analyzer_detects_presence_and_position():
    result = NumberAnalyzer().analyze("5 حقائق ستغير رأيك")
    assert result["value"]["present"] is True
    assert result["value"]["position"] == 0.0


def test_number_analyzer_absent():
    result = NumberAnalyzer().analyze("لا يوجد أرقام هنا")
    assert result["value"]["present"] is False
    assert result["value"]["position"] is None


def test_question_analyzer_detects_arabic_mark():
    result = QuestionAnalyzer().analyze("هل جربت هذا من قبل؟")
    assert result["value"]["present"] is True


def test_question_analyzer_detects_latin_mark():
    result = QuestionAnalyzer().analyze("Did you know this?")
    assert result["value"]["present"] is True


def test_question_analyzer_absent():
    result = QuestionAnalyzer().analyze("This is a statement.")
    assert result["value"]["present"] is False


def test_negation_analyzer():
    assert NegationAnalyzer().analyze("لن تصدق هذا")["value"]["present"] is True
    assert NegationAnalyzer().analyze("this works fine")["value"]["present"] is False


def test_curiosity_analyzer():
    assert CuriosityAnalyzer().analyze("هل تعلم أن الدماغ لا يشعر بالألم")["value"]["present"] is True
    assert CuriosityAnalyzer().analyze("عبارة عادية")["value"]["present"] is False


def test_warning_analyzer():
    assert WarningAnalyzer().analyze("تحذير: خطأ شائع")["value"]["present"] is True
    assert WarningAnalyzer().analyze("عبارة عادية بدون أي كلمات خاصة")["value"]["present"] is False


def test_comparison_analyzer():
    assert ComparisonAnalyzer().analyze("A vs B")["value"]["present"] is True


def test_percentage_analyzer():
    result = PercentageAnalyzer().analyze("90% من الناس يفعلون هذا")
    assert result["value"]["present"] is True


def test_opening_word_analyzer_number():
    assert OpeningWordAnalyzer().analyze("5 حقائق")["value"] == "number"


def test_opening_word_analyzer_interrogative():
    assert OpeningWordAnalyzer().analyze("هل تعلم")["value"] == "interrogative"


def test_opening_word_analyzer_statement():
    assert OpeningWordAnalyzer().analyze("هذا نص عادي")["value"] == "statement"


def test_opening_word_analyzer_empty():
    assert OpeningWordAnalyzer().analyze("")["value"] == "empty"


def test_word_count_analyzer():
    assert WordCountAnalyzer().analyze("one two three")["value"] == 3


def test_character_count_analyzer():
    assert CharacterCountAnalyzer().analyze("abc")["value"] == 3


def test_average_word_length_analyzer():
    result = AverageWordLengthAnalyzer().analyze("aa bbbb")
    assert result["value"] == 3.0  # (2+4)/2


def test_average_word_length_analyzer_empty():
    assert AverageWordLengthAnalyzer().analyze("")["value"] == 0.0


def test_sentence_length_analyzer():
    result = SentenceLengthAnalyzer().analyze("one two three")
    assert result["value"] == 3.0


def test_punctuation_analyzer():
    result = PunctuationAnalyzer().analyze("Wow! Really? Yes.")
    assert result["value"]["count"] == 3
    assert result["value"]["density"] > 0


def test_emoji_analyzer_counts_emoji():
    result = EmojiAnalyzer().analyze("hello 🔥🔥 world")
    assert result["value"] == 2


def test_emoji_analyzer_no_emoji():
    assert EmojiAnalyzer().analyze("plain text")["value"] == 0


def test_colon_usage_analyzer():
    assert ColonUsageAnalyzer().analyze("Warning: danger")["value"] is True
    assert ColonUsageAnalyzer().analyze("no colon here")["value"] is False


def test_parentheses_analyzer():
    assert ParenthesesAnalyzer().analyze("text (extra info)")["value"] is True
    assert ParenthesesAnalyzer().analyze("no parens")["value"] is False


def test_quotation_marks_analyzer():
    assert QuotationMarksAnalyzer().analyze('he said "hi"')["value"] is True
    assert QuotationMarksAnalyzer().analyze("no quotes")["value"] is False


def test_uppercase_ratio_analyzer():
    result = UppercaseRatioAnalyzer().analyze("ABC def")
    assert result["value"] == round(3 / 6, 4)


def test_uppercase_ratio_analyzer_no_latin_letters():
    assert UppercaseRatioAnalyzer().analyze("هل تعلم")["value"] == 0.0


def test_whitespace_pattern_analyzer():
    assert WhitespacePatternAnalyzer().analyze("a   b")["value"] == 1
    assert WhitespacePatternAnalyzer().analyze("a b")["value"] == 0


# ---------------------------------------------------------------------- explainability contract

def _all_analyzer_instances():
    return [
        NumberAnalyzer(), QuestionAnalyzer(), NegationAnalyzer(), CuriosityAnalyzer(),
        WarningAnalyzer(), ComparisonAnalyzer(), PercentageAnalyzer(), OpeningWordAnalyzer(),
        WordCountAnalyzer(), CharacterCountAnalyzer(), AverageWordLengthAnalyzer(),
        SentenceLengthAnalyzer(), PunctuationAnalyzer(), EmojiAnalyzer(), ColonUsageAnalyzer(),
        ParenthesesAnalyzer(), QuotationMarksAnalyzer(), UppercaseRatioAnalyzer(),
        WhitespacePatternAnalyzer(),
    ]


def test_every_analyzer_returns_required_explainability_keys():
    for analyzer in _all_analyzer_instances():
        result = analyzer.analyze("هل تعلم أن 5% من الناس يحبون هذا؟ (تحذير)")
        assert "value" in result
        assert "extraction_method" in result
        assert "source" in result
        assert result["source"] == "hook_text"


def test_every_analyzer_exposes_feature_name_and_version():
    for analyzer in _all_analyzer_instances():
        assert isinstance(analyzer.feature_name, str) and analyzer.feature_name
        assert isinstance(analyzer.version, str) and analyzer.version


def test_every_analyzer_is_deterministic():
    text = "5 أسرار ستغير رأيك للأبد؟"
    for analyzer in _all_analyzer_instances():
        assert analyzer.analyze(text) == analyzer.analyze(text)
