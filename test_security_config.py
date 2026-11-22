import ast
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import restart_clock


class SecurityConfigTests(unittest.TestCase):
    def test_clock_ssh_requires_keys_and_verified_host(self):
        tree = ast.parse(Path(__file__).with_name('clock.py').read_text())
        command = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'RS_CMD' for t in node.targets))
        self.assertEqual(command[0], 'ssh')
        self.assertIn('BatchMode=yes', command)
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertNotIn('sshpass', command)

    @patch('restart_clock.subprocess.run')
    def test_restart_is_noninteractive_and_bounded(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout='active', stderr='')
        self.assertEqual(restart_clock.restart('test@device'), 'active')
        args = run.call_args.args[0]
        self.assertEqual(args[0], 'ssh')
        self.assertIn('BatchMode=yes', args)
        self.assertIn('StrictHostKeyChecking=yes', args)
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertEqual(run.call_args.kwargs['timeout'], 30)
        self.assertNotIn('shell', run.call_args.kwargs)

    @patch('restart_clock.subprocess.run')
    def test_invalid_target_never_invokes_ssh(self, run):
        for value in ['-oProxyCommand=bad', 'host; bad', 'host\nother']:
            with self.assertRaises(ValueError):
                restart_clock.restart(value)
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
