import mock


@mock.patch("cou.cli.entrypoint")
def test_init(cli):
    from cou import __main__  # noqa: F401

    assert cli.call_count == 1
