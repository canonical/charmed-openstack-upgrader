============
Known issues
============

Potential known upgrade bugs and non-standard procedures are listed in the OpenStack Charm Guide:

- `Issues, charm procedures, and OpenStack upgrade notes`_

Manila Ganesha
--------------

The manila-ganesha_ charm was wrongly tracking the version of ceph package instead of the manila
and an error like this can happen when running COU:

.. code:: bash

    [WARNING] Not possible to find the charm manila-ganesha in the lookup
    [ERROR] 'manila-ganesha' with workload version 17.1.0 has no compatible OpenStack release.

In that case ,refresh the current channel of the charm to receive the fix and then run COU again.

.. LINKS:
.. _Issues, charm procedures, and OpenStack upgrade notes: https://docs.openstack.org/charm-guide/latest/project/issues-and-procedures.html
.. _manila-ganesha: https://bugs.launchpad.net/charm-manila-ganesha/+bug/2060751
