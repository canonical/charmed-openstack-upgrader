============
Known issues
============

The following issues are known to the OpenStack charms, and they are not related to **COU**. Some
of the bug reporst might contains potential workarounds. If you encounter those issues, please
check the relevant bug reports for more information.

Ceph
----

Workload version does not changed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

See `bug 2068151`_ and `#401`_ for more details.


Designate
---------

Upgrade causes units in error state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Refreshing designate charm from ``yoga/stable`` to ``zed/stable`` will leave the designate units in
error state. You might find a message in `juju debug` like this

.. code::

    subprocess.CalledProcessError: Command '['/var/lib/juju/agents/unit-designate-1/.venv/bin/pip',
    'install', '-U', '--force-reinstall', '--no-index', '--no-cache-dir', '-f', 'wheelhouse',
    'pyparsing==3.0.9', 'flit-core==3.7.1', 'dnspython==2.2.1', 'pyaml==21.10.1', 'Jinja2==3.0.3',
    'packaging==21.3', 'tomli==1.2.3', 'netifaces==0.11.0', 'netaddr==0.7.19', 'psutil==5.9.2',
    'charms.openstack==0.0.1.dev1', 'pbr==5.10.0', 'charmhelpers==1.1.1.dev86', 'PyYAML==5.3.1',
    'charms.reactive==1.5.1']' returned non-zero exit status 1.

See `bug 2114254`_ for more details.


Manila
------

Workload does not get upgraded
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The configuration based upgrade does not work on certain version of Manila charms. You might find a
message like this

.. code::

    Verify that the workload of 'manila' has been upgraded on units: manila/0, manila/1, manila/2 ✖

    [ERROR] Unit(s) 'manila/0, manila/1, manila/2' did not complete the upgrade
    to zed. Some local processes may still be executing; you may try re-running COU in a few
    minutes.


See `bug 2111738`_ for more details.


Manila Ganesha
--------------

Workload does not get upgraded
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The configuration based upgrade does not work on certain versions of Manila Ganesha charms. You
might find a message like this

.. code::

    Verify that the workload of 'manila-ganesha' has been upgraded on units: manila-ganesha/0,
    manila-ganesha/1, manila-ganesha/2 ✖

    [ERROR] Unit(s) 'manila-ganesha/0, manila-ganesha/1, manila-ganesha/2' did not complete the
    upgrade to zed. Some local processes may still be executing; you may try re-running COU in a
    few minutes.

See `bug 2111738`_ for more details.

Workload version is reported incorrectly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Certain versions of the Manila Ganesha charm incorrectly report their workload version, which can
lead to false positive COU errors resembling the following one:

.. code:: bash

    [WARNING] Not possible to find the charm manila-ganesha in the lookup
    [ERROR] 'manila-ganesha' with workload version 17.1.0 has no compatible OpenStack release.

If affected, refresh the Manila Ganesha charm to its most recent version (within the same release
channel) and re-run **COU**.

See `bug 2060751`_ for details.


Rabbitmq Server
---------------

Upgrade does not work with ``enable-auto-restarts=True``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The rabbitmq-server charm must have ``enable-auto-restarts=False`` for **COU** to work properly due
to the known charm bug.

We suggest that users should temporarily set ``enable-auto-restarts=False`` when performing ``cou
upgrade``, and rollback to original setting after the upgrade is completed.

See `bug 2046381`_ for details.


Additional Information
----------------------

Potential known upgrade bugs and non-standard procedures are listed in the OpenStack Charm Guide:

- `Issues, charm procedures, and OpenStack upgrade notes`_



.. LINKS:
.. _Issues, charm procedures, and OpenStack upgrade notes: https://docs.openstack.org/charm-guide/latest/project/issues-and-procedures.html
.. _bug 2060751: https://bugs.launchpad.net/charm-manila-ganesha/+bug/2060751
.. _bug 2046381: https://bugs.launchpad.net/charm-rabbitmq-server/+bug/2046381
.. _bug 2068151: https://bugs.launchpad.net/charm-ceph-osd/+bug/2068151
.. _#401: https://github.com/canonical/charmed-openstack-upgrader/issues/401
.. _bug 2111738: https://bugs.launchpad.net/charm-manila/+bug/2111738
.. _bug 2114254: https://bugs.launchpad.net/charm-designate/+bug/2114254
