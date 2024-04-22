===============
Upgrade a cloud
===============

Recommendations and guidelines for upgrading production clouds
--------------------------------------------------------------

1. Upgrades can be disruptive; perform them during a maintenance window
2. The **control-plane** must be upgraded before the **data-plane**. Simply use
   `cou upgrade control-plane` without subcommands to ensure the correct ordering of operations.
3. Forcing the upgrade of non-empty hypervisors will disrupt the connectivity of the VMs they are
   hosting; live-migrate instances away from hypervisors undergoing an upgrade if possible
4. Use the `hypervisors` subcommand to test the upgrade of a single `canary machine` before
   upgrading the rest of the **data-plane**.
5. If no issues are found after upgrading the `canary machine`, proceed with the upgrade.

Upgrade the whole cloud
-----------------------

To upgrade the entire OpenStack cloud, including both the **control-plane** and the
**data-plane**, use:

.. code:: bash

    cou upgrade


Upgrade the control-plane
-------------------------

To run an upgrade targeting only the **control-plane** applications use:

.. code:: bash

    cou upgrade control-plane


Upgrade the data-plane
----------------------

To run an upgrade targeting only the **data-plane** applications use:

.. code:: bash

    cou upgrade data-plane

**Note:**

- It's essential to complete the upgrade of the **control-plane** components before
  being able to upgrade the **data-plane**.
- By default, if non-empty hypervisor are identified, they are going to be excluded from the
  upgrade and a warning message will be shown. See the `Upgrade non-empty hypervisors`_
  section for instructions on how to include them.


Upgrade the hypervisors
-----------------------

To upgrade just the **hypervisors** use:

.. code:: bash

    # upgrade for all empty hypervisors
    cou upgrade hypervisors

It's also possible to target specific Juju **availability-zones** or **machines**:

.. code:: bash

    # upgrade for hypervisors with machine ID 0 and 1 (unless they're hosting VMs)
    cou upgrade hypervisors --machine "0, 1"

    # upgrade for all empty hypervisors that are in zone-1
    cou upgrade hypervisors --availability-zone=zone-1

**Note:**

- Those specific filters are mutually exclusive, meaning that it's not possible
  to use them together.
- Since **hypervisors** are part of the **data-plane**, they won't be upgraded unless the
  **control-plane** has already been upgraded.
- By default, if non-empty hypervisor are identified, they are going to be excluded from the
  upgrade and a warning message will be shown. See the `Upgrade non-empty hypervisors`_
  section for instructions on how to include them.

Upgrade non-empty hypervisors
-----------------------------
If it's necessary to upgrade non-empty hypervisors, use the `--force` option. For example:

.. code:: bash

    # upgrade all data-plane applications, including hypervisors currently running instances
    cou upgrade data-plane --force

    # upgrade all hypervisors, even if they are hosting running instances
    cou upgrade hypervisors --force

    # upgrade hypervisors on machines 0 and 1, even if they are hosting running instances
    cou upgrade hypervisors --machine "0, 1" --force

    # upgrade all hypervisors that are in zone-1, even if they are hosting running instances
    cou upgrade hypervisors --availability-zone=zone-1 --force

**Note:** This will disrupt connectivity for any running VM. Migrate them elsewhere before
upgrading if this is undesirable.

Run interactive upgrades
------------------------

By default, **COU** runs upgrade in an interactive mode,  prompting the user to confirm each step.

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
            Wait for up to 2400s for model 'test-model' to reach the idle state
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
        Wait for up to 2400s for model 'test-model' to reach the idle state
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
            Wait for up to 2400s for model 'test-model' to reach the idle state
            Verify that the workload of 'keystone' has been upgraded

    Continue (y/n): y
    Upgrade software packages of 'keystone' from the current APT repositories \

    ...  # apply each step
    Upgrade completed.


Run non-interactive upgrades
----------------------------

**COU** provides a non-interactive mode which suppresses user prompts and automatically
continues executing each planned step. This option allows **COU** to be used by scripts
or during upgrade testing. A quiet mode switch is also offered, which suppresses all
logs and only prints important information including the generated plan and critical
messages like the completion of the upgrade.

Usage examples
~~~~~~~~~~~~~~

Non-interactive mode:

.. terminal::
    :input: cou upgrade --auto-approve

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    ...  # the generated plan
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

    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        Back up MySQL databases
        ...
    Upgrade completed.
