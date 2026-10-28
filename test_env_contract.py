import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from env_contract import check, main, parse


class EnvContractTests(unittest.TestCase):
    def test_nul_in_value_is_rejected_without_disclosure(self):
        result = check('A=', 'A=private\x00value')
        self.assertFalse(result['ok'])
        self.assertIn('invalid_line', [item['kind'] for item in result['findings']])
        self.assertNotIn('private', json.dumps(result))

    def test_hash_without_preceding_space_is_literal(self):
        self.assertTrue(check('A=', 'A=#literal')['ok'])
        self.assertFalse(check('A=', 'A= # comment')['ok'])
        self.assertTrue(check('A=', 'A=value#suffix')['ok'])

    def test_optional_does_not_suppress_malformed_or_duplicate(self):
        for actual in ['A=yes\nB="unterminated', 'A=yes\nB=\nB=']:
            with self.subTest(actual=actual):
                self.assertFalse(check('A=\nB=', actual, optional=['B'])['ok'])

    def test_cli_repeated_optional_keys_and_typo(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            example, actual = Path(directory) / 'example', Path(directory) / 'actual'
            example.write_text('A=\nB=\nC=', encoding='utf-8')
            actual.write_text('A=yes', encoding='utf-8')
            arguments = ['--example', str(example), '--env', str(actual), '--json']
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(arguments + ['--optional', 'B', '--optional', 'C'])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())['ok'])
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as caught:
                main(arguments + ['--optional', 'private-typo'])
            self.assertEqual(caught.exception.code, 2)
            self.assertNotIn('private-typo', error.getvalue())

    def test_optional_key_can_be_missing_or_empty(self):
        for actual in ['A=yes', 'A=yes\nB=']:
            self.assertTrue(check('A=\nB=', actual, optional=['B'])['ok'])

    def test_unknown_optional_key_rejected(self):
        with self.assertRaises(ValueError):
            check('A=', 'A=yes', optional=['TYPO'])

    def test_cli_missing_file_has_safe_error(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            output = io.StringIO()
            with contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as caught:
                main(['--example', str(Path(directory) / 'private-template')])
            self.assertEqual(caught.exception.code, 2)
            self.assertNotIn(directory, output.getvalue())
            self.assertNotIn('private-template', output.getvalue())

    def test_cli_invalid_utf8_has_safe_error(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            example = Path(directory) / 'example'
            example.write_bytes(b'A=private-value\xff')
            output = io.StringIO()
            with contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as caught:
                main(['--example', str(example)])
            self.assertEqual(caught.exception.code, 2)
            self.assertNotIn('private-value', output.getvalue())
            self.assertNotIn(directory, output.getvalue())

    def test_cli_findings_exit_one(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            example, actual = Path(directory) / 'example', Path(directory) / 'actual'
            example.write_text('REQUIRED=', encoding='utf-8')
            actual.write_text('# empty', encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--example', str(example), '--env', str(actual), '--json'])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())['findings'][0]['kind'], 'missing')

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
