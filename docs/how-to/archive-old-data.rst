==========================================
Archive old data
==========================================

By default, **COU** plans for and runs an archive step
before proceeding to actual upgrade steps.
This can be turned off with the ``no-archive`` flag.

This archive step is a performance optimisation,
moving data for soft deleted nova instances into a shadow table.

The archiving is run in batches.
The default batch size is 1000.
On some clouds, it may be desirable to reduce the batch size to reduce database load.
The batch size can be configured with ``archive-batch-size <size>`` where ``size`` is a positive integer.

Usage examples
--------------

With a custom batch size:

.. terminal::
    :input: cou plan --archive-batch-size 200

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        Back up MySQL databases
        Archive old database data on nova-cloud-controller
        Control Plane principal(s) upgrade plan
        ...

Disabling the archive step:

.. terminal::
    :input: cou plan --no-archive

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        Back up MySQL databases
        Control Plane principal(s) upgrade plan
        ...

More information
----------------

- `nova-cloud-controller charm actions`_
- `nova-manage reference`_ - see ``archive_deleted_rows`` subcommand
- OpenStack upgrade guide information on `archiving old database data`_
- :doc:`Purge data on shadow table <purge-data-on-shadow-table>`
- :doc:`Nova data migration <../explanation/nova-data-migration>`


.. LINKS
.. _nova-cloud-controller charm actions: https://charmhub.io/nova-cloud-controller/actions
.. _nova-manage reference: https://docs.openstack.org/nova/rocky/cli/nova-manage.html
.. _archiving old database data: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/wallaby/upgrade-openstack.html#archive-old-database-data
