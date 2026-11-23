"""Original Qt Fincept F2 headless READ ONLY news service: source and runtime QA.

Runtime tests run only with FINCEPT_F2_NATIVE_BIN pointing to the compiled
original Qt binary; no service is installed, no market/broker network access.
"""
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2] / "fincept-qt" / "src"
SOURCE = (ROOT / "app" / "ReadonlyNewsMcpService.cpp").read_text()
MAIN = (ROOT / "app" / "main.cpp").read_text()
SERVER = (ROOT / "mcp" / "server" / "McpHttpServer.cpp").read_text()
NEWS = (ROOT / "services" / "news" / "NewsService.cpp").read_text()


def test_dedicated_entrypoint_bypasses_gui_broker():
    flag = MAIN.index('"--serve-readonly-news"')
    app = MAIN.index("QApplication app(argc, argv)")
    assert flag < app
    assert "run_readonly_news_mcp_service(argc, argv)" in MAIN
    assert 'src/app/ReadonlyNewsMcpService.cpp' in (
        ROOT.parent / "CMakeLists.txt"
    ).read_text()


def test_headless_minimal_original_get_news_only():
    assert 'tools::get_news_tools()' in SOURCE
    assert 'tool.name != QLatin1String("get_news")' in SOURCE
    assert 'McpProvider::instance().tool_count() != 1' in SOURCE
    assert "McpService::instance().initialize()" not in SOURCE
    assert "bootstrap_auth()" not in SOURCE
    assert "IGDemoCanonicalAdapter" not in SOURCE
    assert "get_live_trading_tools" not in SOURCE


def test_strict_readonly_and_cache_only_in_actual_original_service():
    assert 'news.enforce_cache_only_mode()' in SOURCE
    assert 'args.value(QStringLiteral("force")).toBool(false)' in SOURCE
    assert 'CacheManager::instance().get(QStringLiteral("news:articles")).isNull()' in SOURCE
    assert 'FINCEPT_UNAVAILABLE' in SOURCE
    assert "if (cache_only_mode_.load())" in NEWS
    assert "if (d_->readonly_news_service_mode)" in SERVER
    assert "void McpHttpServer::clear_selftest_overrides()" in SERVER
    assert 'd_->shared->allow_actions.store(false)' in SERVER
    assert "port < mcp_http_detail::kMinUserPort" in SERVER
    assert "d_->test_mode || d_->readonly_news_service_mode" in SERVER


def test_private_credentials_without_settings_or_secrets_in_logs():
    assert '::lstat(' in SOURCE
    assert 'st.st_uid == owner && (st.st_mode & 0777) == 0600' in SOURCE
    assert 'st.st_nlink == 1' in SOURCE
    assert '::geteuid() == 0' in SOURCE
    assert 'QString::fromUtf8(qgetenv("FINCEPT_READONLY_NEWS_SERVICE_HOME")) != home' in SOURCE
    assert 'FINCEPT_READONLY_NEWS_SERVICE_ACK' in SOURCE
    assert 'FINCEPT_RESEARCH_ONLY_NO_BROKER_V1' in SOURCE
    assert 'FINCEPT_F2_READONLY_NEWS_READY' in SOURCE
    assert 'SecureStorage::instance().store(' not in SOURCE
    assert 'LOG_INFO' not in SOURCE
    assert 'qDebug()' not in SOURCE


def test_lifecycle_is_bounded_and_no_qa_shortcut():
    assert "std::signal(SIGTERM, handle_term)" in SOURCE
    assert "s_stop_requested" in SOURCE
    assert "stop_poll.setInterval(100)" in SOURCE
    assert "server.stop()" in SOURCE
    assert "CacheDatabase::instance().close()" in SOURCE
    assert "McpHttpServer::set_selftest_overrides" not in SOURCE
    assert "FINCEPT_F2_DENIED_" in SOURCE


def native_bin():
    candidate = os.environ.get("FINCEPT_F2_NATIVE_BIN", "")
    if not candidate:
        pytest.skip("Native binary not supplied: source test only")
    p = Path(candidate)
    assert p.is_file() and p.is_absolute()
    return str(p)


def env_for(home: Path, port: int) -> dict[str, str]:
    env = {
        "HOME": str(home),
        "TMPDIR": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "LC_ALL": "en_US.UTF-8" if sys.platform == "darwin" else "C.UTF-8",
        "QT_QPA_PLATFORM": "offscreen",
        "QT_OPENGL": "software",
        "QT_QUICK_BACKEND": "software",
        # Exact packaged AppImage in rootless --network none Docker has no
        # FUSE device. Preserve extract-and-run into the ephemeral private HOME
        # even though tests deliberately do NOT inherit the host environment.
        "APPIMAGE_EXTRACT_AND_RUN": "1",
        "QTWEBENGINE_DISABLE_SANDBOX": "1",
        "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu --no-sandbox",
        "FINCEPT_READONLY_NEWS_SERVICE_ACK": "FINCEPT_RESEARCH_ONLY_NO_BROKER_V1",
        "FINCEPT_READONLY_NEWS_SERVICE_HOME": str(home),
        "FINCEPT_READONLY_NEWS_MCP_PORT": str(port),
    }
    return env


def private_profile(home: Path, *, insecure: bool = False):
    home.chmod(0o700)
    marker = home / ".fincept-readonly-service-v1"
    token = home / "mcp.token"
    marker.write_text("FINCEPT_RESEARCH_ONLY_NO_BROKER_V1\n")
    token.write_text(secrets.token_urlsafe(64) + "\n")
    marker.chmod(0o600)
    token.chmod(0o644 if insecure else 0o600)
    return token.read_text().strip()


def port_for_test() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def request(port: int, method: str, payload=None, token=None):
    con = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    headers = {"Host": f"127.0.0.1:{port}", "Accept": "application/json, text/event-stream"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        headers["Content-Type"] = "application/json"
    try:
        con.request(method, "/mcp" if payload is not None else "/health",
                    json.dumps(payload) if payload is not None else None, headers)
        r = con.getresponse()
        data = r.read(250000)
        try:
            body = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            body = {}
        return r.status, body
    finally:
        con.close()


def rpc(method, ident=1, params=None):
    return {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}


def test_invalid_permissions_refused_before_qt_or_network():
    binary = native_bin()
    with tempfile.TemporaryDirectory(prefix="fincept-f2-reject-", dir="/private/tmp" if sys.platform == "darwin" else None) as name:
        home = Path(name)
        private_profile(home, insecure=True)
        port = port_for_test()
        cmd = [binary, "--serve-readonly-news"]
        r = subprocess.run(cmd, env=env_for(home, port), capture_output=True,
                           text=True, timeout=12)
        assert r.returncode == 2
        assert "FINCEPT_F2_DENIED_UNSAFE_CREDENTIAL_FILES" in r.stderr
        assert "READY" not in r.stdout


def test_denied_without_explicit_ack_or_ambiguous_argv():
    binary = native_bin()
    with tempfile.TemporaryDirectory(prefix="fincept-f2-no-ack-", dir="/private/tmp" if sys.platform == "darwin" else None) as name:
        home = Path(name)
        private_profile(home)
        env = env_for(home, port_for_test())
        env.pop("FINCEPT_READONLY_NEWS_SERVICE_ACK")
        r = subprocess.run([binary, "--serve-readonly-news"], env=env,
                           capture_output=True, text=True, timeout=12)
        assert r.returncode == 2
        assert "FINCEPT_F2_DENIED_NO_EXPLICIT_OPERATOR_GATE" in r.stderr
        env["FINCEPT_READONLY_NEWS_SERVICE_ACK"] = "FINCEPT_RESEARCH_ONLY_NO_BROKER_V1"
        r = subprocess.run([binary, "--serve-readonly-news", "--profile", "personal"],
                           env=env, capture_output=True, text=True, timeout=12)
        assert r.returncode == 2


def test_actual_original_service_authenticated_cache_only_and_sigterm():
    binary = native_bin()
    with tempfile.TemporaryDirectory(prefix="fincept-f2-native-", dir="/private/tmp" if sys.platform == "darwin" else None) as name:
        home = Path(name)
        bearer = private_profile(home)
        port = port_for_test()
        env = env_for(home, port)
        output_file = home / "test_stdout.log"
        cmd = [binary, "--serve-readonly-news"]
        if sys.platform == "darwin" and os.environ.get("FINCEPT_F2_MAC_SANDBOX_EGRESS_DENIED") == "1":
            policy = '(version 1) (allow default) (deny network-outbound (remote ip "*:*")) (allow network-outbound (remote ip "localhost:*"))'
            cmd = ["/usr/bin/sandbox-exec", "-p", policy, *cmd]
        with output_file.open("w+") as log:
            child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 22
                while time.monotonic() < deadline:
                    if child.poll() is not None:
                        raise AssertionError("Original process exited before MCP ready: " + output_file.read_text(errors="replace")[-1000:])
                    try:
                        status, _ = request(port, "GET")
                        if status == 200:
                            break
                    except (OSError, TimeoutError, http.client.HTTPException):
                        pass
                    time.sleep(.15)
                else:
                    raise AssertionError("Original service did not become healthy")
                assert request(port, "POST", rpc("tools/list"))[0] == 401
                code, resp = request(port, "POST", rpc("tools/list"), bearer)
                assert code == 200, (code, resp)
                tools = resp["result"]["tools"]
                assert {x["name"] for x in tools} == {"get_news"}, tools
                code, resp = request(
                    port, "POST", rpc("tools/call", 4,
                        {"name": "get_quote", "arguments": {"symbol": "AAPL"}}), bearer,
                )
                assert code == 200 and "error" in resp, resp

                code, resp = request(
                    port, "POST", rpc("tools/call", 5,
                        {"name": "get_news", "arguments": {"force": True}}), bearer,
                )
                assert code == 200
                assert resp["result"]["isError"] is True
                assert "FINCEPT_UNAVAILABLE" in json.dumps(resp)

                code, resp = request(
                    port, "POST", rpc("tools/call", 6,
                        {"name": "get_news", "arguments": {"force": False}}), bearer,
                )
                assert code == 200 and resp["result"]["isError"] is True
                assert "FINCEPT_UNAVAILABLE" in json.dumps(resp)

                # This is EXPLICITLY a synthetic, locally seeded cache fixture.
                # No external feed is contacted, no publisher truth asserted.
                data_root = (
                    home / "Library/Application Support/com.fincept.terminal"
                    if sys.platform == "darwin"
                    else home / ".local/share/com.fincept.terminal"
                )
                db = data_root / "profiles/f2_readonly_news/data/cache.db"
                assert db.is_file()
                now = int(time.time())
                article = {
                    "id": "f2-synthetic-001", "headline": "F2 synthetic QA fixture",
                    "summary": "Not real financial news", "category": "MARKETS",
                    "source": "F2-TEST-FIXTURE", "region": "GLOBAL",
                    "sort_ts": now, "publisher_datetime_ts": now,
                    "publisher_datetime_field": "pubDate",
                    "link": "https://example.org/qa-f2-no-network",
                    "time": "just now", "tier": 4, "priority": "ROUTINE",
                    "sentiment": "NEUTRAL", "impact": "LOW", "lang": "en", "tickers": [],
                }
                raw = json.dumps([article], separators=(",", ":"))
                with sqlite3.connect(db, timeout=3) as con:
                    con.execute("""
                        INSERT INTO unified_cache
                          (key,value,category,ttl_seconds,expires_at,size_bytes)
                        VALUES (?,?,?,90,datetime('now','+90 seconds'),?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                          expires_at=excluded.expires_at
                    """, ("news:articles", raw, "f2_synthetic_qa", len(raw)))
                    con.commit()
                code, resp = request(
                    port, "POST", rpc("tools/call", 7,
                        {"name": "get_news", "arguments": {"category": "MARKETS",
                            "time_range": "24H", "limit": 5,
                            "include_publisher_datetime": True}}), bearer,
                )
                assert code == 200 and not resp["result"]["isError"], resp
                content = resp["result"]["structuredContent"]
                assert content["count"] == 1 and content["articles"][0]["headline"] == "F2 synthetic QA fixture"
                assert content["articles"][0]["publisher_datetime_attested"] is False
                # Force refresh still refused, even when cache is valid.
                code, resp = request(
                    port, "POST", rpc("tools/call", 8,
                        {"name": "get_news", "arguments": {"force": True}}), bearer,
                )
                assert resp["result"]["isError"] and "FINCEPT_UNAVAILABLE" in json.dumps(resp)
            finally:
                if child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=4)
        text = output_file.read_text(errors="replace")
        assert child.returncode == 0, (child.returncode, text[-2000:])
        assert "FINCEPT_F2_READONLY_NEWS_READY" in text
        assert "FINCEPT_F2_READONLY_NEWS_STOPPED" in text
        assert bearer not in text
        assert "IGDemoCanonicalAdapter" not in text
