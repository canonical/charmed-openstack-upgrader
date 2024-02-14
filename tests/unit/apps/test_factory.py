#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from unittest.mock import MagicMock, patch

from cou.apps import factory
from cou.utils.juju_utils import COUApplication


@patch.object(factory, "is_charm_supported", return_value=False)
def test_app_factory_not_supported_openstack_charm(mock_is_charm_supported):
    app = MagicMock(spec_set=COUApplication)()
    app.charm = charm = "my_app"
    my_app = factory.AppFactory.create(app)

    assert my_app is None
    mock_is_charm_supported.assert_called_once_with(charm)


@patch.object(factory, "is_charm_supported", return_value=True)
@patch.object(factory, "asdict")
def test_app_factory_register(mock_asdict, mock_is_charm_supported):
    charm = "foo"
    app = MagicMock(spec_set=COUApplication)()
    app.charm = charm

    @factory.AppFactory.register_application([charm])
    class Foo:
        def __init__(self, *_, **__):
            pass

    assert charm in factory.AppFactory.charms
    foo = factory.AppFactory.create(app)

    mock_is_charm_supported.assert_called_once_with(charm)
    mock_asdict.assert_called_once_with(app)
    assert foo is not None
    assert isinstance(foo, Foo)
