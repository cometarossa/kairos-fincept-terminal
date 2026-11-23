"""Static fail-closed QA guard around the original Qt get_news MCP diagnostic.

These checks complement, but cannot replace, compiling and executing the
original Qt app with a real public RSS file and a separate KAIROS client.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "fincept-qt" / "src"
HEADER = (ROOT / "services" / "news" / "NewsService.h").read_text()
SOURCE = (ROOT / "mcp" / "server" / "McpServerSelfTest.cpp").read_text()


def test_original_news_service_parser_and_cache_codec_not_exported():
    assert "friend struct NewsMcpPublicRssQA" in HEADER
    assert "NewsMcpPublicRssQA::parse(source_bytes)" in SOURCE
    assert "NewsMcpPublicRssQA::encode(articles)" in SOURCE
    assert "NewsService::parse_rss_xml(xml, feed)" in SOURCE
    assert "NewsService::serialize_articles(articles)" in SOURCE


def test_news_qa_requires_full_explicit_operator_gate():
    assert 'FINCEPT_PUBLIC_MCP_NEWS_QA' in SOURCE
    assert 'SAVED_PUBLIC_RSS_LOCAL_READ_V1' in SOURCE
    assert 'FINCEPT_PUBLIC_MCP_NEWS_RSS_FILE' in SOURCE
    assert 'FINCEPT_PUBLIC_MCP_NEWS_CLIENT_SCRIPT' in SOURCE
    assert 'FINCEPT_PUBLIC_MCP_NEWS_PYTHON' in SOURCE
    assert 'contains(QStringLiteral("--selftest-mcp-server"))' in SOURCE
    assert 'rss_info.isAbsolute() && rss_info.isFile()' in SOURCE
    assert 'rss_info.size() > 0 && rss_info.size() <= 200000' in SOURCE


def test_news_qa_uses_original_mcp_and_no_provider_refresh_or_second_broker():
    part = SOURCE.split("// F1: actual public-source RSS", 1)[1].split(
        "if (!destructive_tool.isEmpty())", 1
    )[0]
    assert 'QStringLiteral("get_news")' in part
    assert '{"force", false}' in part
    assert 'cache.put(key, payload, 90' in part
    assert 'cache.remove(key);' in part
    assert 'rep.check(clocks_ok,' in part
    assert 'FINCEPT_PUBLIC_MCP_HISTORY_QA' not in part
    assert 'nam_->get' not in part
    assert 'IGDemoCanonicalAdapter' not in part


def test_kairos_external_child_is_bounded_and_never_logs_qa_token():
    part = SOURCE.split("// F1: actual public-source RSS", 1)[1].split(
        "if (!destructive_tool.isEmpty())", 1
    )[0]
    assert 'safe.insert(QStringLiteral("KAIROS_QA_MCP_TEST_TOKEN"), token)' in part
    assert 'safe.insert(QStringLiteral("KAIROS_QA_EXPECT"), expect)' in part
    assert 'QStringLiteral("RECENT")' in part
    assert 'QStringLiteral("STALE")' in part
    assert 'pump_until(' in part and '22000' in part
    assert 'KAIROS_ORIGINAL_FINCEPT_PUBLIC_NEWS_READ_PASS' in part
    assert 'KAIROS_ORIGINAL_FINCEPT_STALE_NEWS_HOLD_PASS' in part
    assert 'child.readAllStandardOutput()' in part
    assert 'out(receipt)' not in part
