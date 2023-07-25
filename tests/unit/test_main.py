import mock


@mock.patch("cou.cli.entrypoint")
def test_init(cli):
    import importlib

    loader = importlib.machinery.SourceFileLoader("__main__", "cou/__main__.py")
    loader.load_module()
    assert cli.call_count == 1
