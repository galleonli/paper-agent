"""Tests for AI summarization behavior (no real network calls)."""

from unittest.mock import patch

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.summarize import _build_research_prompt, _call_openai_chat, build_research_summary


def _paper() -> Paper:
    return Paper(
        id="2501.00001",
        title="Continual Learning with Sparse Experts",
        summary="We study continual learning with sparse expert routing.",
        authors=["Alice", "Bob"],
        categories=["cs.LG"],
        updated="2025-01-02T10:00:00Z",
        link_abs="https://arxiv.org/abs/2501.00001",
        link_pdf=None,
    )


def test_build_research_summary_calls_openai_with_model_and_timeout() -> None:
    """When enabled/provider=openai, pass configured model and timeout to OpenAI helper."""
    cfg = Config()
    cfg.summarize.enabled = True
    cfg.summarize.provider = "openai"
    cfg.summarize.model = "gpt-4.1-mini"
    cfg.summarize.research_summary_enabled = True
    cfg.advanced.request_timeout_seconds = 42

    with patch(
        "paper_agent.core.summarize._call_openai_chat",
        return_value="Structured summary body.",
    ) as call_mock:
        out = build_research_summary(_paper(), "Keyphrase matched", cfg)

    assert out is not None
    heading, body = out
    assert heading == "Research-focused summary"
    assert body == "Structured summary body."
    assert call_mock.call_count == 1
    call_args = call_mock.call_args.args
    assert call_args[1] == "gpt-4.1-mini"
    assert call_args[2] == 42


def test_build_research_summary_returns_none_when_disabled_or_provider_invalid() -> None:
    """Disabled summarize/research toggle or invalid provider should return None."""
    cfg = Config()
    p = _paper()

    cfg.summarize.enabled = False
    assert build_research_summary(p, "why", cfg) is None

    cfg.summarize.enabled = True
    cfg.summarize.research_summary_enabled = False
    assert build_research_summary(p, "why", cfg) is None

    cfg.summarize.research_summary_enabled = True
    cfg.summarize.provider = "unknown-provider"
    assert build_research_summary(p, "why", cfg) is None


def test_build_research_summary_zh_language_heading() -> None:
    """Chinese language setting should return Chinese research-summary heading."""
    cfg = Config()
    cfg.summarize.enabled = True
    cfg.summarize.provider = "openai"
    cfg.summarize.language = "zh"

    with patch(
        "paper_agent.core.summarize._call_openai_chat",
        return_value="这是结构化总结。",
    ):
        out = build_research_summary(_paper(), "why", cfg)

    assert out is not None
    heading, body = out
    assert heading == "研究视角总结"
    assert body == "这是结构化总结。"


def test_build_research_prompt_uses_config_override_template() -> None:
    """Custom prompts.research_summary_template should override the built-in default."""
    cfg = Config()
    cfg.summarize.language = "en"
    cfg.prompts.research_summary_template = (
        "LANG={language_name}\n"
        "TITLE={paper_title}\n"
        "WHY={why_text}\n"
        "KEYPHRASES={keyphrases}\n"
    )

    prompt = _build_research_prompt(_paper(), "Matched by seeds", cfg)

    assert prompt == (
        "LANG=English\n"
        "TITLE=Continual Learning with Sparse Experts\n"
        "WHY=Matched by seeds\n"
        "KEYPHRASES=N/A"
    )


def test_build_research_prompt_falls_back_when_template_placeholder_invalid() -> None:
    """Invalid override placeholders should fall back to the built-in default prompt."""
    cfg = Config()
    cfg.prompts.research_summary_template = "BROKEN={missing_key}"

    prompt = _build_research_prompt(_paper(), "why", cfg)

    assert prompt.startswith("You are a research assistant for machine learning papers.")
    assert "Title: Continual Learning with Sparse Experts" in prompt


def test_call_openai_chat_returns_none_without_api_key() -> None:
    """No OPENAI_API_KEY means helper returns None and does not send request."""
    with (
        patch.dict("os.environ", {}, clear=True),
        patch(
            "paper_agent.core.summarize.requests.post",
            side_effect=AssertionError("requests.post should not be called without OPENAI_API_KEY"),
        ),
    ):
        out = _call_openai_chat("prompt", "gpt-4.1-mini", 30)
    assert out is None


def test_call_openai_chat_sends_model_and_auth_header() -> None:
    """Helper should call Chat Completions endpoint with configured model and bearer key."""

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "ok"}}]}

    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True),
        patch("paper_agent.core.summarize.requests.post", return_value=_Resp()) as post_mock,
    ):
        out = _call_openai_chat("hello", "gpt-4.1-mini", 13)

    assert out == "ok"
    assert post_mock.call_count == 1
    kwargs = post_mock.call_args.kwargs
    assert kwargs["timeout"] == 13
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "gpt-4.1-mini"


def test_build_research_summary_invokes_openai_api_when_key_set() -> None:
    """
    With OPENAI_API_KEY in env and summarize enabled, build_research_summary
    triggers a real requests.post to OpenAI (mocked here). Proves the API path is used.
    """
    cfg = Config()
    cfg.summarize.enabled = True
    cfg.summarize.provider = "openai"
    cfg.summarize.model = "gpt-4o-mini"
    cfg.summarize.research_summary_enabled = True
    cfg.advanced.request_timeout_seconds = 30

    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "API returned this summary."}}]}

    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-123"}, clear=False),
        patch(
            "paper_agent.core.summarize.requests.post",
            return_value=_FakeResponse(),
        ) as post_mock,
    ):
        out = build_research_summary(_paper(), "why", cfg)

    assert out is not None
    heading, body = out
    assert heading == "Research-focused summary"
    assert body == "API returned this summary."
    assert post_mock.call_count == 1
    call_kw = post_mock.call_args.kwargs
    assert call_kw["headers"]["Authorization"] == "Bearer sk-test-key-123"
    assert call_kw["json"]["model"] == "gpt-4o-mini"
    assert "messages" in call_kw["json"] and len(call_kw["json"]["messages"]) >= 1


def test_build_research_summary_returns_none_when_key_missing_even_if_enabled() -> None:
    """With summarize enabled but OPENAI_API_KEY unset, no request is sent and result is None."""
    cfg = Config()
    cfg.summarize.enabled = True
    cfg.summarize.provider = "openai"
    cfg.summarize.research_summary_enabled = True

    with (
        patch.dict("os.environ", {}, clear=True),
        patch(
            "paper_agent.core.summarize.requests.post",
            side_effect=AssertionError("post must not be called when key is missing"),
        ),
    ):
        out = build_research_summary(_paper(), "why", cfg)

    assert out is None
