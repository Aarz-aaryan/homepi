import subprocess, pty, os, time

pid, fd = pty.fork()
if pid == 0:
    # child: exec into SSH with sudo
    os.execvp('sshpass', [
        'sshpass', '-p', '000000', 'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ServerAliveInterval=10',
        '-tt', 'homepi@homepi',
        'sudo', 'systemctl', 'restart', 'clock'
    ])
    os._exit(1)

# parent: write password after delay
time.sleep(1.5)
os.write(fd, b'000000\n')
time.sleep(3)

p = subprocess.run(['sshpass', '-p', '000000', 'ssh', '-o', 'StrictHostKeyChecking=no', 'homepi@homepi',
    'sleep 2 && systemctl status clock --no-pager -n 3'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print(p.stdout.decode()[-500:])
