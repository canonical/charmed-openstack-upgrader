==============
Upgrade Groups
==============

In the process of planning or executing an upgrade for an OpenStack cloud, users have the
capability to target a specific group of applications based on their services responsibilities.

**Note:** COU will upgrade **openstack-dashboard** and **octavia** at the end of the
**control-plane** upgrade (before upgrading **control-plane** subordinate applications
and **data-plane** services) due to the desired upgrade group splits. This is slightly
different from the `upstream upgrade documentation`_.

Control Plane
-------------

The **control-plane** includes services tasked with making decisions related to data management,
routing, and processing. Services considered as **control-plane** in OpenStack and in scope
of COU are (following their upgrade order):

- rabbitmq-server
- ceph-mon
- keystone
- aodh
- barbican
- ceilometer
- ceph-fs
- ceph-radosgw
- cinder
- designate
- designate-bind
- glance
- gnocchi
- heat
- manila
- manila-ganesha
- neutron-api
- neutron-gateway
- ovn-dedicated-chassis
- ovn-central
- placement
- nova-cloud-controller
- openstack-dashboard
- octavia
- additional principal applications that contribute to the formation of the OpenStack cloud 
  (typically **mysql-innodb-cluster** and **vault**)
- **control-plane** subordinate applications


Data Plane
----------

On the other hand, the **data-plane** is composed of services that handle the actual data
transfer. Services considered as **data-plane** in OpenStack and in scope of COU are (following
their upgrade order):

- nova-compute
- any **control-plane** services colocated on the same machines with the **nova-compute**
  application (typically **cinder**)
- ceph-osd
- **data-plane** subordinate applications

**Note:** It's essential to complete the upgrade of the **control-plane** components before
proceeding to any **data-plane** components to ensure cloud functionality.

Hypervisors
-----------

Within the data-plane are **hypervisors**. In COU they represent machines hosting the hypervisor
service (**nova-compute**), which facilitate the distribution of compute and memory resources
among virtual machines (VMs), and other services colocated on the same nodes.

**Note:** Since **hypervisors** comprise a subset of **data-plane** components, it is
also necessary to complete the upgrade of the **control-plane** components before
proceeding to **hypervisors** upgrades.

.. LINKS:
.. _upstream upgrade documentation: https://docs.openstack.org/charm-guide/latest/admin/upgrades/charms.html#upgrade-order