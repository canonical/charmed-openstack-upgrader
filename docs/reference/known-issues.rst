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


Ceph not updating version
-------------------------

Ceph applications might need manual intervention after the upgrade because the payload version
doesn't update automatically. You might find a message like this

.. code::

    [WARNING] Ceph mon (ceph-mon/0) sees mismatched versions in ceph daemons:
    {
        "mon": {
            "ceph version 18.2.4 (e7ad5345525c7aa95470c26863873b581076945d) reef (stable)": 3
        },
        "mgr": {
            "ceph version 18.2.4 (e7ad5345525c7aa95470c26863873b581076945d) reef (stable)": 3
        },
        "osd": {
            "ceph version 17.2.7 (b12291d110049b2f35e32e0de30d70e9a4c060d2) quincy (stable)": 9
        },
        "rgw": {
            "ceph version 17.2.7 (b12291d110049b2f35e32e0de30d70e9a4c060d2) quincy (stable)": 3
        },
        "overall": {
            "ceph version 17.2.7 (b12291d110049b2f35e32e0de30d70e9a4c060d2) quincy (stable)": 12,
            "ceph version 18.2.4 (e7ad5345525c7aa95470c26863873b581076945d) reef (stable)": 6
        }
    }

See `bug 2046381`_ and `#401`_ for more details.


.. LINKS:
.. _Issues, charm procedures, and OpenStack upgrade notes: https://docs.openstack.org/charm-guide/latest/project/issues-and-procedures.html
.. _bug 2060751: https://bugs.launchpad.net/charm-manila-ganesha/+bug/2060751
.. _bug 2046381: https://bugs.launchpad.net/charm-rabbitmq-server/+bug/2046381
.. _#401: https://github.com/canonical/charmed-openstack-upgrader/issues/401
