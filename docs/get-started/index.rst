===========
Get started
===========

Verify Access
-------------
To use **COU** you need to have access to a `Charmed OpenStack`_ cloud, which is deployed
using `Juju`_. **COU** uses Juju credentials to access the OpenStack cloud, so accessing
the cloud with Juju is mandatory. Cloud access verification can be done by simply
calling the juju status command.

.. code:: bash
    
    juju status --model <name-of-your-openstack-model>


**COU** requires at minimum `write` permission to the target model.

Installation
------------
Install the **COU** snap from the `snap store`_:

.. code:: bash
    
    sudo snap install charmed-openstack-upgrader

.. LINKS
.. _Charmed OpenStack: https://ubuntu.com/openstack/docs
.. _Juju: https://juju.is/docs/juju
.. _snap store: https://snapcraft.io/