import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from env_contract import check, main, parse


class EnvContractTests(unittest.TestCase):
    def test_empty_contract_cannot_pass(self):
        result = check('# template accidentally empty', 'TOKEN=present')
        self.assertFalse(result['ok'])
        self.assertEqual(result['findings'][0]['kind'], 'empty_contract')

    def test_matching_contract(self):
        self.assertTrue(check('A=\nB=example', 'export A=one\nB="two" # comment')['ok'])

    def test_missing_and_empty(self):
        result = check('A=\nB=', 'A=""')
        self.assertEqual([x['kind'] for x in result['findings']], ['empty', 'missing'])

    def test_extra_opt_in(self):
        self.assertTrue(check('A=', 'A=yes\nB=more')['ok'])
        self.assertFalse(check('A=', 'A=yes\nB=more', True)['ok'])

    def test_duplicates_both_files(self):
        result = check('A=\nA=', 'A=x\nA=y')
        self.assertEqual([x['source'] for x in result['findings']], ['example', 'env'])

    def test_values_never_in_report(self):
        result = check('A=', 'bad secret-line\nA="secret-value\nA=another-secret')
        report = json.dumps(result)
        self.assertNotIn('secret', report)
        self.assertFalse(result['ok'])

    def test_bom_and_comments(self):
        keys, findings = parse('\ufeff# hi\n\nA=value#literal\nB= # blank\nC="a#b"')
        self.assertEqual(keys, {'A': True, 'B': False, 'C': True})
        self.assertEqual(findings, [])

    def test_bad_quote_and_trailing_garbage(self):
        self.assertFalse(check('A=', 'A="ok" garbage')['ok'])
        self.assertFalse(check('A=', "A='unterminated")['ok'])

    def test_cli_json_and_exit_code(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            example = Path(directory) / 'example'
            actual = Path(directory) / 'actual'
            example.write_text('A=', encoding='utf-8')
            actual.write_text('A=secret-value', encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--example', str(example), '--env', str(actual), '--json'])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())['ok'])
            self.assertNotIn('secret-value', output.getvalue())


if __name__ == '__main__':
    unittest.main()
