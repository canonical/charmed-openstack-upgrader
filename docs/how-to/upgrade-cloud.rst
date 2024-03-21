===============
Upgrade a cloud
===============

Recommendations for upgrading production clouds
-----------------------------------------------

1. Be sure to upgrade in a maintenance window
2. Start with the upgrade on control-plane applications
3. Don't force the upgrade on non-empty hypervisors
4. After upgrading the **control-plane**, choose one empty hypervisor to be a `canary node`.
    After upgrading it, test if it's behaving as expected.
5. If no issues are found after upgrading the `canary node`, proceed with the upgrade.

Run upgrade for the whole cloud
-------------------------------

To upgrade the entire OpenStack cloud, including both the **control-plane** and the
**data-plane**, use:

.. code:: bash

    cou upgrade


Run upgrade for the control-plane
---------------------------------

To run an upgrade targeting the **control-plane** applications use:

.. code:: bash

    cou upgrade control-plane


Run upgrade for the data-plane
------------------------------

To run an upgrade targeting the **data-plane** applications use:

.. code:: bash

    cou upgrade data-plane

**Note:**
- It's essential to complete the upgrade of the **control-plane** components before
being able to upgrade the **data-plane**.
- By default, this command will not upgrade hypervisors that have VMs running. See the
`Upgrade non-empty hypervisors`_ section to include them.


Run upgrade for the hypervisors
-------------------------------

To upgrade just the **hypervisors** use:

.. code:: bash

    cou upgrade hypervisors

It's also possible to target for specific Juju **availability-zones** or **machines**:

.. code:: bash

    # upgrade for just empty hypervisors in machines 0 and 1
    cou upgrade hypervisors --machine "0, 1"

    # upgrade for all empty hypervisors that are into zone-1
    cou upgrade hypervisors --availability-zone=zone-1

**Note:**
- Those specific filters are mutually exclusive, meaning that it's not possible
to use them together.
- Since **hypervisors** comprise a subset of **data-plane** components, it is
also necessary to complete the upgrade of the **control-plane** components before
the **hypervisors** can be upgraded.
- By default, this command will not upgrade hypervisors that have VMs running. See the
`Upgrade non-empty hypervisors`_ section to include them.

Upgrade non-empty hypervisors
-----------------------------
If it's necessary to upgrade non-empty hypervisors, use the `--force` command. For example:

.. code:: bash

    # upgrade data-plane applications using all hypervisors
    cou upgrade data-plane --force

    # upgrade all hypervisors
    cou upgrade hypervisors --force

    # upgrade hypervisors from machines 0 and 1
    cou upgrade hypervisors --machine "0, 1" --force

    # upgrade all hypervisors that are in zone-1
    cou upgrade hypervisors --availability-zone=zone-1 --force

**Note:** This is not safe and might cause problems in the running VMs. The recommendation
is to migrate the VMs and upgrade hypervisors machines that are empty.

Run interactive upgrades
------------------------

Use the **upgrade** command to automatically plan and execute the upgrade of your
cloud. This command runs upgrade in interactive mode by default, requiring the user
to confirm each step.

.. code:: bash

    cou upgrade

Usage example
~~~~~~~~~~~~~

.. terminal::
    :input: cou upgrade

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211917.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        Back up MySQL databases
        Control Plane principal(s) upgrade plan
        Upgrade plan for 'rabbitmq-server' to 'victoria'
            Upgrade software packages of 'rabbitmq-server' from the current APT repositories
                Upgrade software packages on unit 'rabbitmq-server/0'
                Upgrade software packages on unit 'rabbitmq-server/1'
                Upgrade software packages on unit 'rabbitmq-server/2'
            Upgrade 'rabbitmq-server' to the new channel: '3.9/stable'
            Change charm config of 'rabbitmq-server' 'source' to 'cloud:focal-victoria'
            Wait for up to 1800s for model 'test-model' to reach the idle state
            Verify that the workload of 'rabbitmq-server' has been upgraded
        ...
    Would you like to start the upgrade? Continue (y/N): y
    Running cloud upgrade...
    Verify that all OpenStack applications are in idle state ✔
    Back up MySQL databases ✔

    Upgrade plan for 'rabbitmq-server' to 'victoria'
        Upgrade software packages of 'rabbitmq-server' from the current APT repositories
            Upgrade software packages on unit 'rabbitmq-server/0'
            Upgrade software packages on unit 'rabbitmq-server/1'
            Upgrade software packages on unit 'rabbitmq-server/2'
        Upgrade 'rabbitmq-server' to the new channel: '3.9/stable'
        Change charm config of 'rabbitmq-server' 'source' to 'cloud:focal-victoria'
        Wait for up to 1800s for model 'test-model' to reach the idle state
        Verify that the workload of 'rabbitmq-server' has been upgraded

    Continue (y/n): y
    Upgrade plan for 'rabbitmq-server' to 'victoria' ✔

    Upgrade plan for 'keystone' to 'victoria'
            Upgrade software packages of 'keystone' from the current APT repositories
                Upgrade software packages on unit 'keystone/0'
                Upgrade software packages on unit 'keystone/1'
                Upgrade software packages on unit 'keystone/2'
            Upgrade 'keystone' to the new channel: 'victoria/stable'
            Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 1800s for model 'test-model' to reach the idle state
            Verify that the workload of 'keystone' has been upgraded

    Continue (y/n): y
    Upgrade software packages of 'keystone' from the current APT repositories \

    ...  # apply each step
    Upgrade completed.


Run non-interactive upgrades
----------------------------

**COU** provides a non-interactive mode which suppresses user prompts and automatically
continue executing each planned steps. This option allows **COU** to be used by scripts
or during upgrade testing. A quiet mode switch is also offered, which will only output
error logs and a completion message to STDOUT.

Usage examples
~~~~~~~~~~~~~~

Non-interactive mode:

.. terminal::
    :input: cou upgrade --auto-approve

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    ...
    Running cloud upgrade...
    Verify that all OpenStack applications are in idle state ✔
    Back up MySQL databases ✔
    Upgrade software packages of 'keystone' from the current APT repositories ✔
    Upgrade 'keystone' to the new channel: 'victoria/stable' ✔
    ...
    Upgrade completed.


Non-interactive and quiet mode:

.. terminal::
    :input: cou upgrade --auto-approve --quiet

    Upgrade completed.


.. LINKS
.. _all-in-one: https://docs.openstack.org/charm-guide/latest/admin/upgrades/openstack.html#perform-the-upgrade
.. _paused-single-unit: https://docs.openstack.org/charm-guide/latest/admin/upgrades/openstack.html#perform-the-upgrade
