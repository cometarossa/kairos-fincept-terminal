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


@pytest.fixture(scope="session")
def native_bin(tmp_path_factory):
    candidate = os.environ.get("FINCEPT_F2_NATIVE_BIN", "")
    if not candidate:
        pytest.skip("Native binary not supplied: source test only")
    p = Path(candidate)
    assert p.is_file() and p.is_absolute()
    if sys.platform == "linux" and p.suffix == ".AppImage":
        # extract-and-run retains an outer runtime process. A SIGTERM sent
        # to that PID is not proof that the original Qt service received it.
        # Extract the EXACT packaged artifact once, in private QA scratch,
        # then launch its own AppRun directly. This is the proposed daemon
        # launch contract; the raw extract-and-run launcher is NOT certified.
        scratch = tmp_path_factory.mktemp("fincept-f2-appdir")
        scratch.chmod(0o700)
        extraction = subprocess.run(
            [str(p), "--appimage-extract"],
            cwd=scratch,
            env={"HOME": str(scratch), "TMPDIR": str(scratch),
                 "PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=90, check=False,
        )
        assert extraction.returncode == 0, extraction.stderr[-1000:]
        appdir = scratch / "squashfs-root"
        entry = appdir / "AppRun"
        payload = appdir / "usr/bin/FinceptTerminal"
        assert entry.is_file() and os.access(entry, os.X_OK)
        assert payload.is_file() and os.access(payload, os.X_OK)
        assert entry.resolve().is_relative_to(appdir.resolve())
        assert payload.resolve().is_relative_to(appdir.resolve())
        return str(entry)
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


def test_invalid_permissions_refused_before_qt_or_network(native_bin):
    binary = native_bin
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


def test_denied_without_explicit_ack_or_ambiguous_argv(native_bin):
    binary = native_bin
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


def test_actual_original_service_authenticated_cache_only_and_sigterm(native_bin):
    binary = native_bin
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
            child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
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
                if sys.platform == "linux" and Path(binary).name == "AppRun":
                    # No wrapper status masquerading as an actual Qt exit.
                    expected = (Path(binary).parent / "usr/bin/FinceptTerminal").resolve()
                    assert Path(f"/proc/{child.pid}/exe").resolve(strict=True) == expected
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
                if child.returncode != 0:
                    # Only failure cleanup for our isolated test process group.
                    # Never convert forced termination into a PASS.
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        text = output_file.read_text(errors="replace")
        assert child.returncode == 0, (child.returncode, text[-2000:])
        assert "FINCEPT_F2_READONLY_NEWS_READY" in text
        assert "FINCEPT_F2_READONLY_NEWS_STOPPED" in text
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", port)) != 0, "MCP listener survived shutdown"
        assert bearer not in text
        assert "IGDemoCanonicalAdapter" not in text


def test_bounded_ingress_uses_original_parser_and_absolute_expiry():
    assert "NewsService::parse_rss_xml(xml, feed)" in SOURCE
    assert "NewsService::serialize_articles(selected)" in SOURCE
    assert "O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC" in SOURCE
    assert "QXmlStreamReader::DTD" in SOURCE
    assert "xml.toBase64() != encoded" in SOURCE
    assert "captured + kSnapshotTtl" in SOURCE
    assert "captured < last_capture_" in SOURCE
    assert "if (captured == last_capture_)" in SOURCE
    assert 'qgetenv("FINCEPT_READONLY_NEWS_INGRESS_ACK")' in SOURCE
    assert '(inbox && !inbox->ready())' in SOURCE


def test_actual_native_inbox_fresh_tamper_replay_and_absolute_expiry(native_bin):
    import base64
    import hashlib
    from email.utils import formatdate

    with tempfile.TemporaryDirectory(prefix="fincept-f2-inbox-", dir="/private/tmp" if sys.platform == "darwin" else None) as name:
        home = Path(name)
        bearer = private_profile(home)
        directory = home / "ingress"
        directory.mkdir(mode=0o700)
        port = port_for_test()
        env = env_for(home, port)
        env["FINCEPT_READONLY_NEWS_INGRESS_ACK"] = "CNBC_SNAPSHOT_V1"

        def snapshot(captured, *, publisher=None, tamper=False, headline="Synthetic inbox QA"):
            # Local synthetic XML, never a real source claim or broker evidence.
            when = formatdate(captured if publisher is None else publisher, usegmt=True)
            xml = (f'<rss version="2.0"><channel><item><title>{headline}</title>'
                   f'<link>https://www.cnbc.com/qa-only-synthetic.html</link>'
                   f'<pubDate>{when}</pubDate></item></channel></rss>').encode()
            return {"schema": "CNBC_SNAPSHOT_V1",
                    "source_url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
                    "captured_at_unix": captured,
                    "rss_sha256": "0" * 64 if tamper else hashlib.sha256(xml).hexdigest(),
                    "rss_base64": base64.b64encode(xml).decode("ascii")}

        def publish(data):
            tmp = directory / ".next"
            with tmp.open("x") as file:
                json.dump(data, file)
            tmp.chmod(0o600)
            tmp.replace(directory / "snapshot.json")

        def result():
            code, body = request(port, "POST", rpc("tools/call", 42,
                {"name": "get_news", "arguments": {"category": "MARKETS",
                 "time_range": "24H", "limit": 5, "include_publisher_datetime": True}}), bearer)
            assert code == 200
            return body["result"]

        def wait_for(expect_available):
            deadline = time.monotonic() + 9
            while time.monotonic() < deadline:
                r = result()
                if (r.get("isError") is False) == expect_available:
                    return r
                time.sleep(.2)
            pytest.fail("inbox availability did not reach expected state")

        output = home / "inbox.log"
        now = int(time.time())
        # Nearly expired capture must not acquire a new ten-minute lifetime.
        near_expiry = snapshot(now - 593)
        publish(near_expiry)
        cmd = [native_bin, "--serve-readonly-news"]
        if sys.platform == "darwin" and os.environ.get("FINCEPT_F2_MAC_SANDBOX_EGRESS_DENIED") == "1":
            policy = '(version 1) (allow default) (deny network-outbound (remote ip "*:*")) (allow network-outbound (remote ip "localhost:*"))'
            cmd = ["/usr/bin/sandbox-exec", "-p", policy, *cmd]
        with output.open("w+") as log:
            child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    assert child.poll() is None
                    try:
                        if request(port, "GET")[0] == 200:
                            break
                    except (OSError, TimeoutError, http.client.HTTPException):
                        pass
                    time.sleep(.1)
                else:
                    pytest.fail("original inbox service not ready")
                r = wait_for(True)
                assert r["structuredContent"]["articles"][0]["headline"] == "Synthetic inbox QA"
                assert r["structuredContent"]["articles"][0]["publisher_datetime_attested"] is False
                wait_for(False)
                fresh = snapshot(int(time.time()))
                publish(fresh)
                assert wait_for(True)["structuredContent"]["count"] == 1
                bad = dict(fresh, rss_sha256="0" * 64)
                publish(bad)
                assert "FINCEPT_UNAVAILABLE" in json.dumps(wait_for(False))
                # Same capture cannot be used to re-admit after invalidation.
                publish(fresh)
                time.sleep(5.5)
                assert result()["isError"]
                # An older, still-in-window capture cannot roll back the latest.
                publish(snapshot(fresh["captured_at_unix"] - 1))
                time.sleep(5.5)
                assert result()["isError"]
                publish(snapshot(int(time.time()), publisher=int(time.time()) - 172800))
                time.sleep(5.5)
                assert result()["isError"]
                publish(snapshot(int(time.time())))
                assert wait_for(True)["structuredContent"]["count"] == 1
                (directory / "snapshot.json").chmod(0o644)
                assert "FINCEPT_UNAVAILABLE" in json.dumps(wait_for(False))
            finally:
                if child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=4)
        receipt = output.read_text(errors="replace")
        assert child.returncode == 0
        assert "FINCEPT_F2_INGRESS_ACCEPTED" in receipt
        assert "FINCEPT_F2_INGRESS_UNAVAILABLE" in receipt
        assert "FINCEPT_F2_READONLY_NEWS_STOPPED" in receipt
        assert bearer not in receipt
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", port)) != 0


def _capture_module():
    import importlib.util
    path = ROOT.parents[1] / "scripts" / "capture_public_cnbc_rss_f2_v1.py"
    spec = importlib.util.spec_from_file_location("f2_capture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_xml(captured, url="https://www.cnbc.com/qa-synthetic.html"):
    from email.utils import formatdate
    return (f'<rss version="2.0"><channel><item><title>Synthetic QA</title>'
            f'<link>{url}</link><pubDate>{formatdate(captured, usegmt=True)}</pubDate>'
            f'</item></channel></rss>').encode()


def test_capture_producer_atomic_envelope_and_no_replay(tmp_path):
    import base64
    import hashlib
    import stat
    capture = _capture_module()
    directory = tmp_path / "inbox"
    directory.mkdir(mode=0o700)
    if os.geteuid() == 0:
        pytest.skip("producer must run as a non-root user")
    now = int(time.time())
    raw = _capture_xml(now)
    snapshot = capture.build_snapshot(raw, now)
    assert snapshot["rss_sha256"] == hashlib.sha256(raw).hexdigest()
    assert base64.b64decode(snapshot["rss_base64"], validate=True) == raw
    capture.publish(directory, snapshot)
    target = directory / "snapshot.json"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert json.loads(target.read_bytes()) == snapshot
    with pytest.raises(ValueError):
        capture.publish(directory, snapshot)
    assert json.loads(target.read_bytes()) == snapshot
    later = capture.build_snapshot(_capture_xml(now + 1), now + 1)
    capture.publish(directory, later)
    assert json.loads(target.read_bytes()) == later
    assert list(directory.iterdir()) == [target]


@pytest.mark.parametrize("case", ["old", "wrong_host", "doctype", "oversized", "empty"])
def test_capture_producer_refuses_unsafe_or_ineligible_xml(case):
    capture = _capture_module()
    now = int(time.time())
    raw = {"old": _capture_xml(now - 172800),
           "wrong_host": _capture_xml(now, "https://example.org/qa"),
           "doctype": b'<!DOCTYPE rss [<!ENTITY x "bad">]>' + _capture_xml(now),
           "oversized": b"x" * 180001, "empty": b""}[case]
    with pytest.raises(ValueError):
        capture.build_snapshot(raw, now)


def test_capture_producer_preserves_previous_on_unsafe_destination(tmp_path):
    capture = _capture_module()
    if os.geteuid() == 0:
        pytest.skip("producer must run as a non-root user")
    directory = tmp_path / "inbox"
    directory.mkdir(mode=0o700)
    target = directory / "snapshot.json"
    target.write_text("[]")
    target.chmod(0o600)
    now = int(time.time())
    with pytest.raises(ValueError):
        capture.publish(directory, capture.build_snapshot(_capture_xml(now), now))
    assert target.read_text() == "[]"


def test_history_inbox_is_explicit_and_original_decoder_only():
    markets = (ROOT / "services" / "markets" / "MarketDataService.cpp").read_text()
    assert 'FINCEPT_READONLY_HISTORY_INGRESS_ACK' in SOURCE
    assert 'tool.name != QLatin1String("get_history")' in SOURCE
    assert 'configure_readonly_history_inbox(directory)' in SOURCE
    assert 'history_integrity::decode(QJsonDocument::fromJson(bars), now)' in markets
    start = markets.index("void MarketDataService::fetch_history(")
    end = markets.index("QStringList args;", start)
    assert "read_history_inbox(readonly_history_inbox_, symbol, period)" in markets[start:end]
    assert "return; // No PythonRunner fallback" in markets[start:end]


@pytest.mark.parametrize("multi_asset", [False, True])
def test_original_history_inbox_native_valid_stale_and_wrong_symbol(native_bin, multi_asset):
    import base64
    import hashlib
    with tempfile.TemporaryDirectory(prefix="fincept-f2-history-", dir="/private/tmp" if sys.platform == "darwin" else None) as name:
        home = Path(name)
        bearer = private_profile(home)
        inbox = home / "history-ingress"
        inbox.mkdir(mode=0o700)
        port = port_for_test()
        env = env_for(home, port)
        env["FINCEPT_READONLY_HISTORY_INGRESS_ACK"] = ("MULTI_YAHOO_HISTORY_SNAPSHOT_V1" if multi_asset else "SPY_YAHOO_HISTORY_SNAPSHOT_V1")
        now = int(time.time())
        # Synthetic fixture only: not a market quote or completed trading session.
        bars = [{"timestamp": now - 86400, "open": 100, "high": 104,
                 "low": 99, "close": 102, "volume": 500}]
        def publish(rows=bars, captured=now, tamper=False, symbol="SPY", declared_symbol=None):
            target = inbox if symbol == "SPY" else inbox / symbol
            target.mkdir(mode=0o700, exist_ok=True)
            raw = json.dumps(rows, separators=(",", ":")).encode()
            obj = {"schema": "YAHOO_HISTORY_SNAPSHOT_V1",
                   "provider": "Yahoo Finance via original yfinance",
                   "symbol": declared_symbol or symbol, "period": "5d", "interval": "1d",
                   "adjustment": "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE",
                   "captured_at_unix": captured,
                   "bars_base64": base64.b64encode(raw).decode(),
                   "bars_sha256": "0"*64 if tamper else hashlib.sha256(raw).hexdigest()}
            tmp = target / ".next"
            with tmp.open("x") as f: json.dump(obj, f)
            tmp.chmod(0o600)
            tmp.replace(target / "snapshot.json")
        def history(symbol="SPY", period="5d"):
            code, body = request(port, "POST", rpc("tools/call", 9,
                {"name": "get_history", "arguments": {"symbol": symbol,
                    "period": period, "interval": "1d", "limit": 5}}), bearer)
            assert code == 200
            return body["result"]
        cmd = [native_bin, "--serve-readonly-news"]
        if sys.platform == "darwin" and os.environ.get("FINCEPT_F2_MAC_SANDBOX_EGRESS_DENIED") == "1":
            policy = '(version 1) (allow default) (deny network-outbound (remote ip "*:*")) (allow network-outbound (remote ip "localhost:*"))'
            cmd = ["/usr/bin/sandbox-exec", "-p", policy, *cmd]
        output = home / "history.log"
        with output.open("w+") as log:
            child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    assert child.poll() is None
                    try:
                        if request(port, "GET")[0] == 200: break
                    except (OSError, TimeoutError, http.client.HTTPException): pass
                    time.sleep(.1)
                else: pytest.fail("history service not ready")
                code, body = request(port, "POST", rpc("tools/list"), bearer)
                assert code == 200
                assert {t["name"] for t in body["result"]["tools"]} == {"get_news", "get_history"}
                assert history()["isError"]
                publish()
                result = history()
                assert result["isError"] is False
                data = result["structuredContent"]
                assert data["symbol"] == "SPY" and data["count"] == 1
                assert data["bars"][0]["close"] == 102
                assert history("AAPL")["isError"] and history(period="1mo")["isError"]
                for symbol in ["EURUSD=X","GBPUSD=X","JPY=X","AUDUSD=X","CAD=X","^GSPC","^NDX","^GDAXI","AAPL","BTC-USD","GC=F"]:
                    publish(symbol=symbol)
                    r = history(symbol)
                    if multi_asset:
                        assert r["isError"] is False
                        assert r["structuredContent"]["symbol"] == symbol
                    else:
                        assert r["isError"]
                if multi_asset:
                    publish(symbol="EURUSD=X", declared_symbol="SPY")
                    assert history("EURUSD=X")["isError"]
                    assert not history()["isError"]
                    publish(symbol="EURUSD=X")
                    (inbox / "EURUSD=X").chmod(0o755)
                    assert history("EURUSD=X")["isError"]
                    (inbox / "EURUSD=X").chmod(0o700)
                    (inbox / "EURUSD=X" / "snapshot.json").unlink()
                    (inbox / "EURUSD=X").rmdir()
                    (inbox / "EURUSD=X").symlink_to(inbox, target_is_directory=True)
                    assert history("EURUSD=X")["isError"]
                assert history("../SPY")["isError"] and history("ZZZ")["isError"]
                publish(tamper=True)
                assert history()["isError"]
                publish(captured=now-901)
                assert history()["isError"]
                publish(rows=[dict(bars[0], low=110)])
                assert history()["isError"]
                publish()
                assert history()["isError"] is False
                (inbox / "snapshot.json").chmod(0o644)
                assert history()["isError"]
            finally:
                if child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try: child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=4)
        receipt = output.read_text(errors="replace")
        assert child.returncode == 0 and "FINCEPT_F2_READONLY_NEWS_STOPPED" in receipt
        assert bearer not in receipt


def _history_capture_module():
    import importlib.util
    scripts = ROOT.parents[1] / "scripts"
    spec = importlib.util.spec_from_file_location("f2_history_capture", scripts / "capture_public_yahoo_history_f2_v1.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))
    return module


def test_history_capture_integrity_and_original_adjustment_contract():
    import base64
    import hashlib
    capture = _history_capture_module()
    now = int(time.time())
    bars = [{"timestamp": now-86400, "open": 100, "high": 104,
             "low": 99, "close": 102, "volume": 500}]
    snapshot = capture.build_snapshot(bars, now)
    raw = base64.b64decode(snapshot["bars_base64"], validate=True)
    assert json.loads(raw) == bars
    assert hashlib.sha256(raw).hexdigest() == snapshot["bars_sha256"]
    assert snapshot["adjustment"] == "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE"
    assert snapshot["symbol"] == "SPY"


@pytest.mark.parametrize("case", ["missing", "nan", "bool", "volume", "ohlc", "future", "stale", "duplicate", "empty"])
def test_history_capture_rejects_invalid_series(case):
    capture = _history_capture_module()
    now = int(time.time())
    bar = {"timestamp": now-86400, "open": 100, "high": 104, "low": 99, "close": 102, "volume": 500}
    cases = {"missing": [{k:v for k,v in bar.items() if k != "volume"}],
             "nan": [dict(bar, close=float("nan"))], "bool": [dict(bar, open=True)],
             "volume": [dict(bar, volume=0.5)], "ohlc": [dict(bar, high=99)],
             "future": [dict(bar, timestamp=now+1)], "stale": [dict(bar,timestamp=now-8*86400)],
             "duplicate": [bar,bar], "empty": []}
    with pytest.raises(ValueError):
        capture.build_snapshot(cases[case], now)


def test_history_capture_no_opt_in_never_imports_provider(tmp_path, monkeypatch):
    capture = _history_capture_module()
    monkeypatch.delenv("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK", raising=False)
    with pytest.raises(ValueError, match="explicit opt-in"):
        capture.capture(tmp_path)
    assert not list(tmp_path.iterdir())


def test_multi_history_producer_allowlist_and_legacy_opt_in(tmp_path, monkeypatch):
    capture = _history_capture_module()
    markets = (ROOT / "services" / "markets" / "MarketDataService.cpp").read_text()
    assert capture.ALLOWED_SYMBOLS == frozenset(["SPY","EURUSD=X","GBPUSD=X","JPY=X","AUDUSD=X","CAD=X","^GSPC","^NDX","^GDAXI","AAPL","BTC-USD","GC=F"])
    for symbol in capture.ALLOWED_SYMBOLS:
        assert '"'+symbol+'"' in markets
    now = int(time.time())
    bar = {"timestamp": now-86400, "open": 100, "high": 104, "low": 99, "close": 102, "volume": 0}
    for symbol in capture.ALLOWED_SYMBOLS:
        assert capture.build_snapshot([bar], now, symbol)["symbol"] == symbol
    monkeypatch.setenv("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK", capture.ACK)
    with pytest.raises(ValueError, match="explicit opt-in"):
        capture.capture(tmp_path, "EURUSD=X")
    with pytest.raises(ValueError, match="symbol denied"):
        capture.capture(tmp_path, "../SPY")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("symbol", ["SPY", "EURUSD=X"])
def test_six_month_capture_requires_depth_and_explicit_ack(symbol, tmp_path, monkeypatch):
    capture = _history_capture_module()
    now = int(time.time())
    bars = [{"timestamp": now-(120-i)*129600, "open": 100, "high": 104,
             "low": 99, "close": 102, "volume": 0} for i in range(120)]
    assert capture.build_snapshot(bars, now, symbol, "6mo")["period"] == "6mo"
    for invalid in (bars[:99], bars[-100:][:99], bars + bars, [dict(x,timestamp=now-120+i) for i,x in enumerate(bars)]):
        with pytest.raises(ValueError):
            capture.build_snapshot(invalid, now, symbol, "6mo")
    with pytest.raises(ValueError, match="window denied"):
        capture.build_snapshot(bars, now, "AAPL", "6mo")
    monkeypatch.setenv("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK", capture.MULTI_ACK)
    with pytest.raises(ValueError, match="explicit opt-in"):
        capture.capture(tmp_path, symbol, "6mo")
    assert not list(tmp_path.iterdir())
