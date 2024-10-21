============
Known issues
============

Potential known upgrade bugs and non-standard procedures are listed in the OpenStack Charm Guide:

- `Issues, charm procedures, and OpenStack upgrade notes`_

Manila Ganesha
--------------

Certain versions of the manila-ganesha charm incorrectly report their workload version, which
can lead to false positive COU errors resembling the following one:


.. code:: bash

    [WARNING] Not possible to find the charm manila-ganesha in the lookup
    [ERROR] 'manila-ganesha' with workload version 17.1.0 has no compatible OpenStack release.

See `bug 2060751`_ for details.

If affected, refresh the manila-ganesha charm to its most recent version (within the same release
channel) and re-run COU.

Rabbitmq Server
---------------

The rabbitmq-server charm must have `enable-auto-restarts=False` for **COU** to
work properly due to the known charm bug.

See `bug 2046381`_ for details.

We suggest that users should temporarily set `enable-auto-restarts=False` when
performing `cou upgrade`, and rollback to original setting after the upgrade is
completed.

.. LINKS:
.. _Issues, charm procedures, and OpenStack upgrade notes: https://docs.openstack.org/charm-guide/latest/project/issues-and-procedures.html
.. _bug 2060751: https://bugs.launchpad.net/charm-manila-ganesha/+bug/2060751
.. _bug 2046381: https://bugs.launchpad.net/charm-rabbitmq-server/+bug/2046381
