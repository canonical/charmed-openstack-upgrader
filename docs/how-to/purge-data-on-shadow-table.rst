==========================================
Purge data on shadow tables
==========================================

The purge step is disable by default. When enabled, it will run before proceeding to actual upgrade steps.
This can be enabled with the ``--purge`` flag.

This purge step is a performance optimisation, delete data from the shadow tables in nova database. The behaviour is equal to run juju action ``purge`` on nova-cloud-controller unit, which help to reduce the size of the database, make queries faster, backups efficiency, and follow the data retention policies.

The ``purge-before-date`` flag is supported to delete the data older than the date provided. The date string format should be YYYY-MM-DD[HH:mm][:ss]. This flag is useful to retain recent data for debugging or data retention policies.


Usage examples
--------------

.. terminal::
   :input cou plan --purge --purge-before-date 2000-01-02


More information
----------------

- `nova-cloud-controller charm actions`_
- `nova-manage reference`_ - see `purge` subcommand
- :doc:`Archive old data <how-to/archive-old-data>`
- :doc:`Nova data migration <explanation/nova-data-migration>`

.. LINKS
.. _nova-cloud-controller charm actions: https://charmhub.io/nova-cloud-controller/actions
.. _nova-manage reference: https://docs.openstack.org/nova/rocky/cli/nova-manage.html
