=======
Upgrade
=======

This phase is responsible for applying the upgrade plan step by step (see
:doc:`Upgrade a cloud <../how-to/upgrade-cloud>`).

For the **control-plane**, COU upgrades applications in a strict sequential
manner, following a predefined order (see :doc:`Upgrade groups <./upgrade-groups>`) and
halting the process should any application encounter an upgrade failure. All
applications within the **control-plane** employ an `all-in-one`_ method, upgrading
all units of an application simultaneously.

COU adopts a more cautious strategy when upgrading **data-plane** applications to
minimize the risk of downtime, which can occur if the unit undergoing upgrade is
actively handling client requests. Between applications, similar to the
**control-plane**, upgrades are executed sequentially following the predefined order
(see :doc:`Upgrade groups <./upgrade-groups>`). But for applications that support the
**openstack-upgrade** action (such as **nova-compute** and its colocated services like
**cinder**), COU handles the upgrades in a `paused-single-unit`_ fashion. This method
is notably more time-intensive, so to streamline the process while still maintaining
cloud stability, units are grouped based on the Juju availability zones of their
respective hosting machines. COU then progresses through these availability zone groups
in a sequential manner, performing upgrades on units within a single zone in parallel.

**Note:** **ceph-osd**, while being a component of the **data-plane**, employs the
*all-in-one* method for upgrades. because its charm is designed to maintain service
availability throughout the upgrade process.

.. LINKS
.. _all-in-one: https://docs.openstack.org/charm-guide/latest/admin/upgrades/openstack.html#perform-the-upgrade
.. _paused-single-unit: https://docs.openstack.org/charm-guide/latest/admin/upgrades/openstack.html#perform-the-upgrade