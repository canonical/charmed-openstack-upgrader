===========
Get started
===========

This section guides you through steps to prepare the environment and install the application.

Verify Access
-------------
To use **COU** you need to have access to a `Charmed OpenStack`_ cloud, which is deployed
using `Juju`_. **COU** uses Juju credentials to access the OpenStack cloud, so accessing
the cloud with Juju is mandatory.

**COU** requires at minimum *write* permission to the target model (see
`User access levels`_ for more information). To verify your current
user's model-scoped access level, run the following Juju command and look for
your OpenStack model.

.. code:: bash

    juju models

Installation
------------
Install the **COU** snap from the `Snap Store`_:

.. code:: bash

    sudo snap install charmed-openstack-upgrader

.. LINKS
.. _Charmed OpenStack: https://ubuntu.com/openstack/docs
.. _Juju: https://documentation.ubuntu.com/juju/latest/
.. _User access levels: https://documentation.ubuntu.com/juju/latest/user/reference/user/#user-access-levels
.. _Snap Store: https://snapcraft.io/
