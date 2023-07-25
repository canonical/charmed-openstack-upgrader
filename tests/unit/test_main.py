import importlib

import mock


@mock.patch("cou.cli.entrypoint")
def test_init(cli):
    loader = importlib.machinery.SourceFileLoader("__main__", "cou/__main__.py")
    loader.load_module()
    cli.assert_called_once_with()
