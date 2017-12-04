import os
import subprocess
import sys

try:
    import pty
except ImportError:
    PTY = False
else:
    PTY = True

os.environ['__MKLIBPY_SUPPRESS_DEPRECATION_WARNING'] = '1'

from mklibpy.common.string import AnyString
from mklibpy.terminal.colored_text import get_text, remove_switch
from mklibpy.util.path import CD

__author__ = 'Michael'

TIMEOUT = 0.5


def system_call(*args, **kwargs):
    out = subprocess.check_output(*args, **kwargs)
    return out.decode().splitlines(False)


if PTY:
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
            if not line.startswith("*"):
                continue
            return line.lstrip("*").strip()


class LsGit(object):
    def __init__(self, stdout=None):
        self.stdout = stdout
        if stdout is None:
            self.stdout = sys.stdout

    @property
    def is_tty(self):
        return self.stdout.isatty()

    @property
    def is_gnu(self):
        try:
            system_call(['ls', '--version'], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def print(self, *args, **kwargs):
        print(*args, **kwargs, file=self.stdout)

    def __call__(self, *args):
        LsGitProcess(self, args).run()


class LsGitProcess(object):
    def __init__(self, parent, args):
        self.__parent = parent
        self.__args = args
        self.__cmd = ['ls'] + list(self.__args)

        self.__flags = None
        self.__options = None
        self.__dirs = None
        self.__cur_dir = None

        self.__parse_args()

    def __parse_args(self):
        self.__flags = AnyString([
            arg
            for arg in self.__args
            if arg.startswith('-') and not arg.startswith('--')
        ])
        self.__options = AnyString([
            arg
            for arg in self.__args
            if arg.startswith('--')
        ])
        self.__dirs = [
            arg
            for arg in self.__args
            if not arg.startswith('-')
        ]

    @property
    def _l(self):
        return 'l' in self.__flags

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
            return 'G' in self.__flags

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

    def __native_call(self):
        return subprocess.check_call(self.__cmd, stdout=self.__parent.stdout)

    def __system_call(self):
        return system_call(self.__cmd)

    if PTY:
        def __system_call_pty(self):
            return system_call_pty(self.__cmd)

    def run(self):
        if not self._l:
            self.__native_call()
            return

        if self.__dirs:
            self.__cur_dir = self.__dirs[0]
        else:
            self.__cur_dir = os.getcwd()

        if not PTY:
            # See Issue #3
            lines = self.__system_call()
            workaround_flag = True
        elif not self.__color:
            lines = self.__system_call()
            workaround_flag = False
        else:
            # This is a workaround for a bug on Mac. See Issue #1 on GitHub
            try:
                lines = self.__system_call_pty()
                workaround_flag = False
            except subprocess.TimeoutExpired:
                lines = self.__system_call()
                workaround_flag = True

        if not workaround_flag:
            for line in lines:
                self.__parent.print(self.__process_line(line))

        else:
            new_lines = []
            modified_flag = False
            for line in lines:
                if modified_flag:
                    self.__parent.print(self.__process_line(line))
                    continue

                new_line = self.__process_line(line)
                if new_line == line:
                    new_lines.append(line)
                    continue

                modified_flag = True
                for line0 in new_lines:
                    self.__parent.print(line0)
                self.__parent.print(new_line)

            if not modified_flag:
                self.__native_call()


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
