import os
import subprocess
import sys
import termios

from mklibpy.terminal.colored_text import get_text
from mklibpy.util.path import CD

__author__ = 'Michael'


def is_tty(fd):
    try:
        termios.tcgetattr(fd)
    except termios.error:
        return False
    else:
        return True


def system_call(*args, **kwargs):
    out = subprocess.check_output(*args, **kwargs)
    return out.decode().splitlines(False)


def is_git_repo(abspath):
    path = os.path.join(abspath, ".git")
    return os.path.exists(path) and os.path.isdir(path)


def get_git_branch(abspath):
    with CD(abspath):
        for line in system_call(['git', 'branch']):
            sp = line.split()
            if "*" not in sp:
                continue
            return sp[1]


class LsGit(object):
    def __init__(self, stdout=None, color=True):
        self.__stdout = stdout
        if stdout is None:
            self.__stdout = sys.stdout
        self.__color = is_tty(self.__stdout) and color

    def print(self, *args, **kwargs):
        print(*args, **kwargs, file=self.__stdout)

    def color(self, text, color=None, mode=None):
        if not self.__color:
            return text
        return get_text(text, color=color, mode=mode)

    def process_line(self, line, env):
        if line.endswith(':') and line[:-1] in env['dirs']:
            env['cur_dir'] = line[:-1]
            return line

        sp = line.split()
        if len(sp) < 9:
            return line

        dir = sp[8]
        abspath = os.path.abspath(os.path.join(env['cur_dir'], dir))
        if not is_git_repo(abspath):
            return line

        branch = get_git_branch(abspath)
        return line + self.color(" ({})".format(branch), color='red', mode='bold')

    def __call__(self, *args):
        dirs = [arg for arg in args if not arg.startswith('-')]

        if dirs:
            cur_dir = dirs[0]
        else:
            cur_dir = os.getcwd()

        env = {
            'dirs': dirs,
            'cur_dir': cur_dir,
        }

        for line in system_call(['ls', '-l'] + list(args)):
            print(self.process_line(line, env))


def main(args=None):
    if args is None:
        import sys
        args = sys.argv[1:]

    instance = LsGit()
    try:
        instance(*args)
    except subprocess.CalledProcessError as e:
        exit(e.returncode)


if __name__ == '__main__':
    main()
