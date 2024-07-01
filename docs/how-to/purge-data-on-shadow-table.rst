==========================================
Purge data on shadow tables
==========================================

The purge steps is disable by default and plans to run before proceeding to actual upgrade steps.
This can be turn on with the `--purge`` flag.

This purge step is a performance optimisation, delete data from the shadow tables in nova database. The behavior is equal to run juju action `purge` on nova-cloud-controller unit.

The `purge-before-date` flag is supported to delete the data older than the date provided. The date string format should be YYYY-MM-DD[HH:mm][:ss].


Usage examples
--------------

.. terminal::
   :input cou plan --purge --purge-before-date 2000-01-02


More information
----------------

- `nova-cloud-controller charm actions`_
- `nova-manage reference`_ - see `purge` subcommand

.. LINKS
.. _nova-cloud-controller charm actions: https://charmhub.io/nova-cloud-controller/actions
.. _nova-manage reference: https://docs.openstack.org/nova/rocky/cli/nova-manage.html
