"""Negative tests: test-only HTTP CONNECT proxy must NEVER reach a broker."""
import unittest
from public_yahoo_only_connect_proxy_v1 import parse_connect, APPROVED


class ProxyPolicyTest(unittest.TestCase):
    def test_exact_allowlisted_market_data_hosts_only(self):
        self.assertEqual(len(APPROVED), 4)
        for h in APPROVED:
            self.assertEqual(parse_connect(f'CONNECT {h}:443 HTTP/1.1\r\n'.encode()), h)

    def test_refuses_every_broker_and_lan_host(self):
        for value in (
            'CONNECT api.ig.com:443 HTTP/1.1',
            'CONNECT demo-api.ig.com:443 HTTP/1.1',
            'CONNECT query1.finance.yahoo.com.evil.tld:443 HTTP/1.1',
            'CONNECT www.google.com:443 HTTP/1.1',
            'CONNECT localhost:443 HTTP/1.1',
            'CONNECT 127.0.0.1:443 HTTP/1.1',
            'CONNECT query1.finance.yahoo.com:80 HTTP/1.1',
            'GET https://query1.finance.yahoo.com/ HTTP/1.1',
            'CONNECT query1.finance.yahoo.com:443 HTTP/2',
            'CONNECT query1.finance.yahoo.com:443 HTTP/1.1 extra',
        ):
            with self.subTest(request=value):
                self.assertIsNone(parse_connect(value.encode()))

    def test_invalid_bytes_and_unbounded_authorities(self):
        for line in (b'CONNECT :443 HTTP/1.1', b'', b'CONNECT query1.finance.yahoo.com:443\xff HTTP/1.1'):
            self.assertIsNone(parse_connect(line))


if __name__ == '__main__':
    unittest.main()
