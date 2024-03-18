==============
Upgrade Groups
==============

In the process of planning or executing an upgrade for an OpenStack cloud, users have the
capability to target a specific group of components based on their operational roles. 

Control Plane
-------------

The **control-plane** includes services tasked with making decisions related to data management,
routing, and processing. Services considered as **control-plane** in OpenStack and in scope
of COU are:

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
- subordinate services that are not collocated with **data-plane** nodes 


Data Plane
----------

On the other hand, the **data-plane** is composed of services that handle the actual data
transfer. Services considered as **data-plane** in OpenStack and in scope of COU are:

- nova-compute
- ceph-osd
- any **control-plane** services collocated on the same nodes with data-plane components

**Note:** It's essential to complete the upgrade of the **control-plane** components before
proceeding to any **data-plane** components to ensure cloud functionality.

Hypervisors
-----------

Within the data-plane are **hypervisors**. In COU they represents nodes hosting the hypervisor
service (**nova-compute**), which facilitate the distribution of compute and memory resources
among virtual machines (VMs), and other services collocated on the same nodes.

**Note:** Since **hypervisors** comprise a subset of **data-plane** components, it is
also necessary to complete the upgrade of the **control-plane** components before
proceeding to **hypervisors** upgrades.