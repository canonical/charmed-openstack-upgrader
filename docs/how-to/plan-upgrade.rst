================
Plan an upgrade
================

The **plan** command is used to generate the upgrade plan; the result will be
printed on STDOUT.


Plan for the whole cloud
------------------------

To generate a plan for the entire OpenStack cloud, including both the **control-plane** and the
**data-plane**, use:

.. code:: bash

    cou plan

Output example
^^^^^^^^^^^^^^

.. terminal::
    :input: cou plan

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        Back up MySQL databases
        Control Plane principal(s) upgrade plan
            Upgrade plan for 'keystone' to 'victoria'
                Upgrade software packages of 'keystone' from the current APT repositories
                    Upgrade software packages on unit 'keystone/0'
                Refresh 'keystone' to the latest revision of 'ussuri/stable'
                Change charm config of 'keystone' 'action-managed-upgrade' to 'False'
                Upgrade 'keystone' to the new channel: 'victoria/stable'
                Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
                Wait for up to 1800s for model 'test_model' to reach the idle state
                Verify that the workload of 'keystone' has been upgraded on units: keystone/0
        Control Plane subordinate(s) upgrade plan
            Upgrade plan for 'keystone-ldap' to 'victoria'
                Refresh 'keystone-ldap' to the latest revision of 'ussuri/stable'
                Upgrade 'keystone-ldap' to the new channel: 'victoria/stable'
        Upgrading all applications deployed on machines with hypervisor.
            Upgrade plan for 'az-1' to 'victoria'
                Disable nova-compute scheduler from unit: 'nova-compute/0'
                Upgrade software packages of 'nova-compute' from the current APT repositories
                    Upgrade software packages on unit 'nova-compute/0'
                Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
                Change charm config of 'nova-compute' 'action-managed-upgrade' to 'True'
                Upgrade 'nova-compute' to the new channel: 'victoria/stable'
                Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
                Upgrade plan for units: nova-compute/0
                    Upgrade plan for unit 'nova-compute/0'
                        Verify that unit 'nova-compute/0' has no VMs running
                        ├── Pause the unit: 'nova-compute/0'
                        ├── Upgrade the unit: 'nova-compute/0'
                        ├── Resume the unit: 'nova-compute/0'
                Enable nova-compute scheduler from unit: 'nova-compute/0'
                Wait for up to 1800s for model 'test_model' to reach the idle state
                Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0
        Remaining Data Plane principal(s) upgrade plan
            Upgrade plan for 'ceph-osd' to 'victoria'
                Verify that all 'nova-compute' units has been upgraded
                Upgrade software packages of 'ceph-osd' from the current APT repositories
                    Upgrade software packages on unit 'ceph-osd/0'
                Change charm config of 'ceph-osd' 'source' to 'cloud:focal-victoria'
                Wait for up to 300s for app 'ceph-osd' to reach the idle state
                Verify that the workload of 'ceph-osd' has been upgraded on units: ceph-osd/0
        Data Plane subordinate(s) upgrade plan
            Upgrade plan for 'ovn-chassis' to 'victoria'
                Refresh 'ovn-chassis' to the latest revision of '22.03/stable'

Plan for the control-plane
--------------------------

To generate a plan targeting only the **control-plane** applications use:

.. code:: bash

    cou plan control-plane

Plan for the data-plane
-----------------------

To generate a plan targeting only the **data-plane** applications use:

.. code:: bash

    cou plan data-plane

**Note:**

- It's essential to complete the upgrade of the **control-plane** components before being able to
  generate a plan for the **data-plane**.
- By default, if non-empty hypervisor are identified, they are going to be excluded from the
  planning and a warning message will be shown. See the `Plan for non-empty hypervisors`_
  section for instructions on how to include them.


Plan for the hypervisors
------------------------

To generate a plan targeting just the **hypervisors** use:

.. code:: bash

    # plan for all empty hypervisors
    cou plan hypervisors

It's also possible to target specific Juju **availability-zones** or **machines**:

.. code:: bash

    # plan for hypervisors with machine ID 0 and 1 (unless they're hosting VMs)
    cou plan hypervisors --machine "0, 1"

    # plan for all empty hypervisors that are in zone-1
    cou plan hypervisors --availability-zone=zone-1

**Note:**

- Those specific filters are mutually exclusive, meaning that it's not possible
  to use them together.
- Since **hypervisors** are part of the **data-plane**, they won't be upgraded unless the
  **control-plane** has already been upgraded.
- By default, if non-empty hypervisor are identified, they are going to be excluded from the
  planning and a warning message will be shown. See the `Plan for non-empty hypervisors`_
  section for instructions on how to include them.


Plan for non-empty hypervisors
------------------------------

If it's necessary to plan for non-empty hypervisors, use the `--force` option. For example:

.. code:: bash

    # plan for all data-plane applications, including hypervisors currently running instances
    cou plan data-plane --force

    # plan for all hypervisors, even if they are hosting running instances
    cou plan hypervisors --force

    # plan for hypervisors on machines 0 and 1, even if they are hosting running instances
    cou plan hypervisors --machine "0, 1" --force

    # plan for all hypervisors that are in zone-1, even if they are hosting running instances
    cou plan hypervisors --availability-zone=zone-1 --force
