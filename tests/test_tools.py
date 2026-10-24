import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/self-hosted-vpn-speedup/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load('generate_mihomo_parallel')
benchmark = load('benchmark_proxy')


def fixture():
    return {'proxies': [
        {'name': 'My VPS', 'type': 'hysteria2', 'server': '192.0.2.10', 'port': 443,
         'password': 'example-only-password', 'sni': 'vpn.example.net',
         'skip-cert-verify': False, 'fingerprint': 'example-only-pin',
         'up': '1 mbps', 'down': '2 mbps'},
        {'name': 'Other', 'type': 'direct'}],
        'proxy-groups': [{'name': 'Proxy', 'type': 'select', 'proxies': ['Other', 'My VPS']}],
        'rules': ['MATCH,Proxy'], 'dns': {'enable': True}}


class GeneratorTests(unittest.TestCase):
    def test_independent_aliases_preserve_auth_tls_and_source(self):
        source = fixture()
        original = copy.deepcopy(source)
        result = generator.build_config(source, 'My VPS', 16, selector='Proxy')
        group = result['proxy-groups'][-1]
        self.assertEqual(group['strategy'], 'round-robin')
        self.assertEqual(len(set(group['proxies'])), 16)
        aliases = result['proxies'][2:]
        for node in aliases:
            self.assertEqual({k: v for k, v in node.items() if k != 'name'},
                             {k: v for k, v in original['proxies'][0].items() if k != 'name'})
        aliases[0]['password'] = 'changed'
        self.assertEqual(aliases[1]['password'], 'example-only-password')
        self.assertEqual(source, original)
        self.assertEqual(result['rules'], original['rules'])
        self.assertEqual(result['proxies'][1], original['proxies'][1])
        self.assertEqual(result['proxy-groups'][0]['proxies'][0], group['name'])

    def test_tuning_is_explicit_and_applies_to_base_and_all_aliases(self):
        untouched = generator.build_config(fixture(), 'My VPS', 2)
        self.assertIn('down', untouched['proxies'][0])
        self.assertNotIn('max-stream-receive-window', untouched['proxies'][0])
        result = generator.build_config(fixture(), 'My VPS', 4,
                                        remove_rate_hints=True, large_windows=True)
        for node in [result['proxies'][0]] + result['proxies'][2:]:
            self.assertNotIn('up', node)
            self.assertNotIn('down', node)
            for key, value in generator.WINDOWS.items():
                self.assertEqual(node[key], value)
            self.assertFalse(node['skip-cert-verify'])

    def test_collisions_fail_without_mutation(self):
        source = generator.build_config(fixture(), 'My VPS', 2)
        before = copy.deepcopy(source)
        with self.assertRaises(ValueError):
            generator.build_config(source, 'My VPS', 2)
        self.assertEqual(source, before)

    def test_chained_node_is_rejected(self):
        source = fixture()
        source['proxies'][0]['dialer-proxy'] = 'Other'
        with self.assertRaises(ValueError):
            generator.build_config(source, 'My VPS', 2)

    def test_invalid_count_selector_or_type_is_rejected(self):
        for count in (0, 257):
            with self.assertRaises(ValueError):
                generator.build_config(fixture(), 'My VPS', count)
        with self.assertRaises(ValueError):
            generator.build_config(fixture(), 'My VPS', 2, selector='Missing')
        with self.assertRaises(ValueError):
            generator.build_config(fixture(), 'Other', 2)

    def test_private_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'candidate.json'
            generator.write_private_json(path, fixture())
            with self.assertRaises(FileExistsError):
                generator.write_private_json(path, {'replaced': True})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), fixture())
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_cli_does_not_print_private_payload(self):
        with tempfile.TemporaryDirectory() as work:
            source, output = Path(work) / 'source.json', Path(work) / 'candidate.json'
            source.write_text(json.dumps(fixture()), encoding='utf-8')
            proc = subprocess.run([sys.executable, str(SCRIPTS / 'generate_mihomo_parallel.py'),
                                   '--input', str(source), '--node', 'My VPS', '--count', '2',
                                   '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn('example-only-password', proc.stdout + proc.stderr)
            self.assertTrue(json.loads(proc.stdout)['candidate_created'])


class BenchmarkTests(unittest.TestCase):
    def test_aggregate_uses_wall_time(self):
        rows = [{'complete': True, 'downloaded_bytes': 10_000_000} for _ in range(4)]
        self.assertEqual(benchmark.summarize(rows, 2)['aggregate_MB_s'], 20)

    def test_partial_work_never_claims_valid_throughput(self):
        rows = [{'complete': True, 'downloaded_bytes': 10_000_000},
                {'complete': False, 'downloaded_bytes': 5_000_000}]
        report = benchmark.summarize(rows, 2)
        self.assertFalse(report['valid'])
        self.assertIsNone(report['aggregate_MB_s'])

    def test_http_error_and_short_body_fail(self):
        for status, size in ((403, 10), (206, 9)):
            raw = {'http_code': status, 'size_download': size, 'time_total': 1}
            with patch.object(benchmark.subprocess, 'run', return_value=
                              subprocess.CompletedProcess([], 0, json.dumps(raw), '')):
                self.assertFalse(benchmark.download('https://example.net/a',
                                                     'http://127.0.0.1:7890', 10, 10, True)['complete'])

    def test_curl_process_uses_explicit_proxy_and_discards_body(self):
        raw = {'http_code': 206, 'size_download': 10, 'time_total': 1}
        with patch.object(benchmark.subprocess, 'run', return_value=
                          subprocess.CompletedProcess([], 0, json.dumps(raw), '')) as run:
            row = benchmark.download('https://example.net/a', 'http://127.0.0.1:7890', 10, 10, True)
        args = run.call_args.args[0]
        self.assertTrue(row['complete'])
        self.assertEqual(args[args.index('--noproxy') + 1], '')
        self.assertEqual(args[args.index('--output') + 1], os.devnull)
        self.assertEqual(args[args.index('--range') + 1], '0-9')

    def test_network_failure_is_an_invalid_sample(self):
        with patch.object(benchmark.subprocess, 'run', side_effect=OSError('local test')):
            self.assertFalse(benchmark.download('https://example.net/a',
                                                 'http://127.0.0.1:7890', 10, 10, True)['complete'])


if __name__ == '__main__':
    unittest.main()
