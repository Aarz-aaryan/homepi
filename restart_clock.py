#!/usr/bin/env python3
"""Restart the remote clock using pre-provisioned SSH keys and narrow sudo rights."""
import os
import re
import subprocess


def restart(target=None):
    target = target or os.environ.get('HOMEPI_SSH_TARGET', 'homepi@homepi')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*', target):
        raise ValueError('Invalid SSH target')
    result = subprocess.run(
        ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
         '-o', 'ConnectTimeout=8', target,
         'sudo -n systemctl restart clock && systemctl status clock --no-pager -n 3'],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return result.stdout


if __name__ == '__main__':
    print(restart())
