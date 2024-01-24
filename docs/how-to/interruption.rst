===============================
Interrupt and resume an upgrade
===============================

Since a partially executed upgrade step can leave the cloud in an inconsistent state,
**COU** ensures upgrades can be interrupted only in between steps. By doing so, upgrades
can be safely stopped and resumed later on.

Abort
-----

In interactive mode, the user must approve each step, and has a chance to interrupt
the process at any prompt.

Usage example:

.. terminal::
    :input: cou upgrade

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
    ...
    Running cloud upgrade...
    Verify that all OpenStack applications are in idle state ✔
    Backup mysql databases ✔
    Upgrade plan for 'keystone' to victoria
        Upgrade software packages of 'keystone' from the current APT repositories
            Upgrade software packages on unit keystone/0
            Upgrade software packages on unit keystone/1
            Upgrade software packages on unit keystone/2
        Upgrade 'keystone' to the new channel: 'victoria/stable'
        Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
        Wait 1800s for model test-model to reach the idle state.
        Check if the workload of 'keystone' has been upgraded

    Would you like to start the upgrade? Continue (y/N): n

SIGINT or SIGTERM signals
-------------------------

**COU** will exit upon receiving SIGINT or SIGTERM signals, but if the upgrade is already
in progress one of two behaviours will occur. If SIGINT or SIGTERM is sent only once
(e.g. by pressing *ctrl+c* once), currently running steps will be allowed to finish,
but any further upgrade step will be cancelled. If **COU** receives two or more SIGINTs
(e.g. by pressing *ctrl+c* multiple times) or SIGTERMs, the upgrade will be cancelled
abruptly in a potentially unsafe way: currently running steps will be immediately
stopped, and no further step will be executed. This is generally not recommended as
the cloud may be left in an inconsistent state.

Exiting before running upgrade plan:

.. terminal::
    :input: cou upgrade - # ctrl+c is pressed while connecting to the controller

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connecting to 'default' model... ✖
    charmed-openstack-upgrader has been terminated
    :input: cou upgrade # ctrl+c is pressed while the cloud is being analyzed
    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connecting to 'default' model... ✔
    Analyzing cloud... ✖
    charmed-openstack-upgrader has been terminated

Safe cancel:

.. terminal::
    :input: cou upgrade # ctrl+c is pressed once during the upgrade

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    ...
    Running cloud upgrade...
    Canceling upgrade... (Press ctrl+c again to stop immediately) ✔
    charmed-openstack-upgrader has been stopped safely

Unsafe cancel:

.. terminal::
    :input: cou upgrade # ctrl+c is pressed twice during the upgrade

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    ...
    Running cloud upgrade...
    Canceling upgrade... (Press ctrl+c again to stop immediately) ✖
    charmed-openstack-upgrader has been terminated without waiting
