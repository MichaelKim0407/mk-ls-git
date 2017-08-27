import os
import pty
import subprocess
import sys
import termios

from mklibpy.common.string import AnyString
from mklibpy.terminal.colored_text import get_text, remove_switch
from mklibpy.util.path import CD

__author__ = 'Michael'

TIMEOUT = 0.5


def system_call(*args, **kwargs):
    out = subprocess.check_output(*args, **kwargs)
    return out.decode().splitlines(False)


def system_call_pty(*args, **kwargs):
    """
    Opens a pty for stdout, so that colored output is retained.
    """
    master, slave = pty.openpty()
    p = subprocess.Popen(*args, **kwargs, stdout=slave)
    code = p.wait(timeout=TIMEOUT)
    if code != 0:
        raise subprocess.CalledProcessError(code, args[0])

    # echo an empty line so that we can properly break
    subprocess.call(['echo', ''], stdout=slave)

    def __gen():
        with os.fdopen(master) as f:
            for line in f:
                line = line.strip()
                if not line:
                    break
                yield line

    return __gen()


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
    def __init__(self, stdout=None):
        self.__stdout = stdout
        if stdout is None:
            self.__stdout = sys.stdout

    @property
    def is_tty(self):
        try:
            termios.tcgetattr(self.__stdout)
        except termios.error:
            return False
        else:
            return True

    @property
    def is_gnu(self):
        try:
            system_call(['ls', '--version'], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def print(self, *args, **kwargs):
        print(*args, **kwargs, file=self.__stdout)

    def __call__(self, *args):
        LsGitProcess(self, args).run()


class LsGitProcess(object):
    def __init__(self, parent, args):
        self.__parent = parent
        self.__args = args
        self.__cmd = ['ls'] + list(self.__args)

        self.__options = None
        self.__dirs = None
        self.__cur_dir = None

        self.__parse_args()

    def __parse_args(self):
        self.__options = AnyString([arg for arg in self.__args if arg.startswith('-')])
        self.__dirs = [arg for arg in self.__args if not arg.startswith('-')]

    @property
    def _l(self):
        return 'l' in self.__options

    @property
    def __color(self):
        if self.__parent.is_gnu:
            if not self.__options.startswith('--color'):
                return False
            if self.__options == '--color' or self.__options == '--color=always':
                return True
            elif self.__options == '--color=auto':
                return self.__parent.is_tty
            else:
                return False

        else:
            if not self.__parent.is_tty:
                return False
            return 'G' in self.__options

    def color(self, text, color=None, mode=None):
        if not self.__color:
            return text
        return get_text(text, color=color, mode=mode)

    def __process_line(self, line):
        if line.endswith(':') and line[:-1] in self.__dirs:
            self.__cur_dir = line[:-1]
            return line

        sp = line.split()
        if len(sp) < 9:
            return line

        dir = sp[8]
        if self.__color:
            dir = remove_switch(dir)

        abspath = os.path.abspath(os.path.join(self.__cur_dir, dir))
        if not is_git_repo(abspath):
            return line

        branch = get_git_branch(abspath)
        return line + self.color(" ({})".format(branch), color='red', mode='bold')

    def run(self):
        if not self._l:
            subprocess.check_call(self.__cmd)
            return

        if self.__dirs:
            self.__cur_dir = self.__dirs[0]
        else:
            self.__cur_dir = os.getcwd()

        if not self.__color:
            lines = system_call(self.__cmd)
        else:
            # This is a workaround for a bug on Mac. See Issue #1 on GitHub
            try:
                lines = system_call_pty(self.__cmd)
            except subprocess.TimeoutExpired:
                lines = system_call(self.__cmd)

        for line in lines:
            self.__parent.print(self.__process_line(line))


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
