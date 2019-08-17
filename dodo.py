import glob
import subprocess

from doit.action import CmdAction


PACKAGE = "efb_wechat_slave"
README_BASE = "./readme_translations/en_US.rst"
DEFAULT_BUMP_MODE = "alpha"
# major, minor, patch, alpha, beta, dev, post
DOIT_CONFIG = {
    "default_tasks": ["msgfmt"]
}


def task_gettext():
    pot = "./{package}/locale/{package}.pot".format(package=PACKAGE)
    sources = glob.glob("./{package}/**/*.py".format(package=PACKAGE), recursive=True)
    sources = [i for i in sources if "__version__.py" not in i]
    command = "xgettext --add-comments=TRANSLATORS -o " + pot + " " + " ".join(sources)
    sources.append(README_BASE)
    return {
        "actions": [
            command,
            ['cp', README_BASE, './.cache/README.rst'],
            ['sphinx-build', '-b', 'gettext', '-C', '-D', 'master_doc=README',
             '-D', 'gettext_additional_targets=literal-block,image',
             './.cache', './readme_translations/locale/', './.cache/README.rst'],
            ['rm', './.cache/README.rst'],
        ],
        "targets": [
            pot
        ],
        "file_dep": sources
    }


def task_msgfmt():
    languages = [i[i.rfind('/') + 1:i.rfind('.')] for i in glob.glob("./readme_translations/locale/*.po")]

    try:
        languages.remove("zh_CN")
    except ValueError:
        pass

    sources = glob.glob("./{package}/**/*.po".format(package=PACKAGE), recursive=True)
    dests = [i[:-3] + ".mo" for i in sources]
    actions = [["msgfmt", sources[i], "-o", dests[i]] for i in range(len(sources))]

    actions.append(["mkdir", "./.cache/source"])
    actions.append(["cp", README_BASE, "./.cache/source/README.rst"])
    for i in languages:
        actions.append(["sphinx-build", "-E", "-b", "rst", "-C",
                        "-D", f"language={i}", "-D", "locale_dirs=./readme_translations/locale",
                        "-D", "extensions=sphinxcontrib.restbuilder",
                        "-D", "master_doc=README", "./.cache/source", f"./.cache/{i}"])
        actions.append(["mv", f"./.cache/{i}/README.rst", f"./readme_translations/{i}.rst"])
        actions.append(["rm", "-rf", f"./.cache/{i}"])
    actions.append(["rm", "-rf", "./.cache/source"])

    return {
        "actions": actions,
        "targets": dests,
        "file_dep": sources,
        "task_dep": ['crowdin', 'crowdin_pull']
    }


def task_crowdin():
    sources = glob.glob("./{package}/**/*.po".format(package=PACKAGE), recursive=True)
    sources.append("readme_translations/en_US.rst")
    return {
        "actions": ["crowdin upload sources"],
        "file_dep": sources,
        "task_dep": ["gettext"]
    }


def task_crowdin_pull():
    return {
        "actions": ["crowdin download"]
    }


def task_commit_lang_file():
    def git_actions():
        if subprocess.run(['git', 'diff-index', '--quiet', 'HEAD']).returncode != 0:
            return ["git commit -m \"Sync localization files from Crowdin\""]
        return ["echo"]

    return {
        "actions": [
            ["git", "add", "*.po", "readme_translations/*.rst"],
            CmdAction(git_actions)
        ],
        "task_dep": ["crowdin", "crowdin_pull"]
    }


def task_bump_version():
    def gen_bump_version(mode=DEFAULT_BUMP_MODE):
        return './bump.py ' + mode

    return {
        "actions": [CmdAction(gen_bump_version)],
        "params": [
            {
                "name": "Version bump mode",
                "short": "b",
                "long": "bump",
                "default": DEFAULT_BUMP_MODE,
                "help": "{major}.{minor}.{patch}{(a|b)}{.post}{.dev}",
                "choices": [
                    ("major", "Bump a major version"),
                    ("minor", "Bump a minor version"),
                    ("patch", "Bump a patch version"),
                    ("alpha", "Bump to the next alpha version"),
                    ("alpha", "Bump to the next beta version"),
                    ("post", "Bump to the next post version"),
                    ("dev", "Bump a dev version (for commit only)")
                ]
            }
        ],
        "task_dep": ["test", "mypy", "commit_lang_file"]
    }


def task_mypy():
    actions = ["mypy -p {}".format(PACKAGE)]
    sources = glob.glob("./{package}/**/*.py".format(package=PACKAGE), recursive=True)
    sources = [i for i in sources if "__version__.py" not in i]
    return {
        "actions": actions,
        "file_dep": sources
    }


def task_test():
    # Unit test is not yet available for EWS
    # sources = glob.glob("./{package}/**/*.py".format(package=PACKAGE), recursive=True)
    # sources = [i for i in sources if "__version__.py" not in i]
    return {
        "actions": [
            # "coverage run --source ./{} -m pytest".format(PACKAGE),
            # "coverage report"
        ],
        # "file_dep": sources
    }


def task_build():
    return {
        "actions": [
            "python setup.py sdist bdist_wheel"
        ],
        "task_dep": ["test", "msgfmt", "bump_version"]
    }


def task_publish():
    def get_twine_command():
        __version__ = __import__(PACKAGE).__version__.__version__
        if 'dev' in __version__:
            raise ValueError(f"Cannot publish dev version ({__version__}).")
        binarys = glob.glob("./dist/*{}*".format(__version__), recursive=True)
        return " ".join(["twine", "upload"] + binarys)
    return {
        "actions": [CmdAction(get_twine_command)],
        "task_dep": ["build"]
    }
