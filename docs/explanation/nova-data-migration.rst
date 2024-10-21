==========================================
Data Migration on nova-cloud-controller
==========================================

This document explains the details of the database migration for nova-cloud-controller.

nova-cloud-controller Database Migration Details
------------------------------------------------

When users upgrade the Juju application nova-cloud-controller, the commands **nova-manage db sync** and **nova-manage db online_data_migration** will be executed.

* **nova-manage db sync** - Upgrades the main database schema to the most recent version.
* **nova-manage db online_data_migration** - Performs data migration to update all live data.

db sync
~~~~~~~

Before the Yoga version, nova-cloud-controller used SQLAlchemy to handle database migrations. Starting from Yoga, it switched to Alembic, a migrations tool for SQLAlchemy.

Below is a table showing the migration versions from Ussuri to Caracal.

.. list-table::
   :header-rows: 1

   * - Version
     - Migration Version
   * - Ussuri
     - 407
   * - Victoria
     - 412
   * - Wallaby
     - 417
   * - Xena
     - 422
   * - Yoga
     - 422
       - (move to Alembic)
       - ``8f2f1571d55b_initial_version``
       - ``16f1fbcab42b_resolve_shadow_table_diffs``
   * - Zed
     - ``ccb0fa1a2252_add_encryption_fields_to``
   * - 2023.1 (Antelope)
     - ``960aac0e09ea_de_duplicate_indexes_in_instances``
   * - 2023.2 (Bobcat)
     - ``1acf2c98e646_add_compute_id_to_instance``
       - ``1b91788ec3a6_drop_legacy_migrate_version_table``
   * - 2024.1 (Caracal)
     - ``13863f4e1612_create_share_mapping_table``

Details of each migration can be found at:

- `unmaintained/yoga - nova/nova/db/main/legacy_migrations/versions`_
- `2024.1 - nova/nova/db/main/migrations/versions`_

db online_data_migration
~~~~~~~~~~~~~~~~~~~~~~~~

The list of online data migrations can be found at `nova_online_migrations`_.
There are only two online migration cases after Victoria:

- ``pci_device_obj.PciDevice.populate_dev_uuids``, added in Victoria
- ``instance_obj.populate_instance_compute_id``, added in 2023.2

On COU
------

Generally, the data migration operation load is not too high, as observed from previous information. COU provides two optional steps, **purge** and **archive**, to reduce the possible load during the upgrade. These two COU steps run the following commands on the nova-cloud-controller Juju unit:

* **db archive_deleted_rows** - Run during the archive step; this command moves deleted rows from production tables to shadow tables.
* **db purge** - Run during the purge step; this command deletes rows from shadow tables.

Make sure to check the details of database schema migrations and online data migrations before each upgrade.

Performing **archive** and **purge** before the cloud upgrade or during a maintenance window is generally recommended, since it can

- optimize the upgrade process
- reduce the database size and disk usage
- improve performance of database queries during cloud operation since the database is smaller

Please refer to the following documentation on how to run **archive** and **purge** step in **COU**.

More Information
----------------

- `opendev/openstack/nova`_
- :doc:`Archive old data <../how-to/archive-old-data>`
- :doc:`Purge data on shadow table <../how-to/purge-data-on-shadow-table>`

.. LINKS
.. _unmaintained/yoga - nova/nova/db/main/legacy_migrations/versions: https://opendev.org/openstack/nova/src/branch/unmaintained/yoga/nova/db/main/legacy_migrations/versions
.. _2024.1 - nova/nova/db/main/migrations/versions: https://opendev.org/openstack/nova/src/branch/stable/2024.1/nova/db/main/migrations/versions
.. _opendev/openstack/nova: https://opendev.org/openstack/nova
.. _nova_online_migrations: https://opendev.org/openstack/nova/src/commit/fcda90460f6831b67027c19ded655b5e7c5e5a1e/nova/cmd/manage.py#L195
