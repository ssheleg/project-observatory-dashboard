"""Compatibility checks for the old CLI and isolated full-engine launcher."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from observatory import cli
from observatory import full_cli


class FullLauncherTests(unittest.TestCase):
    def test_existing_commands_still_parse(self):
        for command in ['init', 'doctor', 'demo', 'scan', 'status', 'dashboard', 'export']:
            self.assertEqual(cli.parser().parse_args([command]).cmd, command)

    def test_home_precedence_and_separate_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(full_cli.full_home(), Path.home() / '.local/share/project-observatory-full')
        with patch.dict(os.environ, {'OBSERVATORY_HOME': '/private/old', 'OBSERVATORY_FULL_HOME': '/private/new'}, clear=True):
            self.assertEqual(full_cli.full_home(), Path('/private/new'))
            self.assertEqual(full_cli.full_home('/private/explicit'), Path('/private/explicit'))

    def test_portable_state_refused_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            (home / 'config.json').write_text('{"private":"synthetic"}')
            before = (home / 'config.json').read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), patch.object(full_cli.subprocess, 'run') as run:
                self.assertEqual(full_cli.run(['init'], str(home)), 2)
                run.assert_not_called()
            self.assertEqual((home / 'config.json').read_bytes(), before)
            self.assertEqual(len(list(home.iterdir())), 1)

    def test_subprocess_preserves_arguments_and_exit(self):
        with patch.object(full_cli.subprocess, 'run') as run:
            run.return_value.returncode = 2
            with tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(full_cli.run(['upgrade', '--apply', '--writers-stopped'], str(Path(tmp).resolve())), 2)
            argv = run.call_args.args[0]
            self.assertEqual(argv[-3:], ['upgrade', '--apply', '--writers-stopped'])
            self.assertTrue(run.call_args.kwargs['env']['OBSERVATORY_HOME'])
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_full_help_and_path_are_nonmutating_routes(self):
        self.assertTrue(cli.parser().parse_args(['full', '--help']).engine_help)
        with patch('observatory.full_cli.run', return_value=0) as run:
            self.assertEqual(cli.main(['full', '--help']), 0)
            run.assert_called_once_with(['--help'], None)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['full-path']), 0)
        self.assertEqual(Path(out.getvalue().strip()), full_cli.engine_path())


if __name__ == '__main__':
    unittest.main()
