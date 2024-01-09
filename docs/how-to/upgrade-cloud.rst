===============
Upgrade a cloud
===============

Run interactive upgrades
------------------------

Use the **upgrade** command to automatically plan and execute the upgrade of your
cloud. This command runs upgrade in interactive mode by default, requiring the user
to confirm each step.

.. code::
    
    $ cou upgrade

Usage example
^^^^^^^^^^^^^

.. code::

    $ cou upgrade
    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211917.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        Backup mysql databases
        Control Plane principal(s) upgrade plan
        Upgrade plan for 'rabbitmq-server' to victoria
            Upgrade software packages of 'rabbitmq-server' from the current APT repositories
            Upgrade 'rabbitmq-server' to the new channel: '3.9/stable'
            Change charm config of 'rabbitmq-server' 'source' to 'cloud:focal-victoria'
            Wait 1800s for model test-model to reach the idle state.
            Check if the workload of 'rabbitmq-server' has been upgraded
        Upgrade plan for 'keystone' to victoria
            Upgrade software packages of 'keystone' from the current APT repositories
            Upgrade 'keystone' to the new channel: 'victoria/stable'
            Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 1800s for model test-model to reach the idle state.
            Check if the workload of 'keystone' has been upgraded
        Upgrade plan for 'cinder' to victoria
            Upgrade software packages of 'cinder' from the current APT repositories
            Refresh 'cinder' to the latest revision of 'ussuri/stable'
            Upgrade 'cinder' to the new channel: 'victoria/stable'
            Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 300s for app cinder to reach the idle state.
            Check if the workload of 'cinder' has been upgraded
        Upgrade plan for 'glance' to victoria
            Upgrade software packages of 'glance' from the current APT repositories
            Upgrade 'glance' to the new channel: 'victoria/stable'
            Change charm config of 'glance' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 300s for app glance to reach the idle state.
            Check if the workload of 'glance' has been upgraded
        Upgrade plan for 'neutron-api' to victoria
            Upgrade software packages of 'neutron-api' from the current APT repositories
            Upgrade 'neutron-api' to the new channel: 'victoria/stable'
            Change charm config of 'neutron-api' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 300s for app neutron-api to reach the idle state.
            Check if the workload of 'neutron-api' has been upgraded
        Upgrade plan for 'neutron-gateway' to victoria
            Upgrade software packages of 'neutron-gateway' from the current APT repositories
            Upgrade 'neutron-gateway' to the new channel: 'victoria/stable'
            Change charm config of 'neutron-gateway' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 300s for app neutron-gateway to reach the idle state.
            Check if the workload of 'neutron-gateway' has been upgraded
        Upgrade plan for 'placement' to victoria
            Upgrade software packages of 'placement' from the current APT repositories
            Upgrade 'placement' to the new channel: 'victoria/stable'
            Change charm config of 'placement' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 300s for app placement to reach the idle state.
            Check if the workload of 'placement' has been upgraded
        Upgrade plan for 'nova-cloud-controller' to victoria
            Upgrade software packages of 'nova-cloud-controller' from the current APT repositories
            Refresh 'nova-cloud-controller' to the latest revision of 'ussuri/stable'
            Upgrade 'nova-cloud-controller' to the new channel: 'victoria/stable'
            Change charm config of 'nova-cloud-controller' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 300s for app nova-cloud-controller to reach the idle state.
            Check if the workload of 'nova-cloud-controller' has been upgraded
        Upgrade plan for 'mysql' to victoria
            Upgrade software packages of 'mysql' from the current APT repositories
            Change charm config of 'mysql' 'source' to 'cloud:focal-victoria'
            Wait 1800s for app mysql to reach the idle state.
            Check if the workload of 'mysql' has been upgraded
        Control Plane subordinate(s) upgrade plan
        Upgrade plan for 'neutron-openvswitch' to victoria
            Upgrade 'neutron-openvswitch' to the new channel: 'victoria/stable'
    Would you like to start the upgrade? Continue (y/N): y
    Running cloud upgrade...
    Verify that all OpenStack applications are in idle state ✔
    Backup mysql databases ✔

    Upgrade plan for 'rabbitmq-server' to victoria
        Upgrade software packages of 'rabbitmq-server' from the current APT repositories
        Upgrade 'rabbitmq-server' to the new channel: '3.9/stable'
        Change charm config of 'rabbitmq-server' 'source' to 'cloud:focal-victoria'
        Wait 1800s for model test-model to reach the idle state.
        Check if the workload of 'rabbitmq-server' has been upgraded

    Continue (y/n): y
    Upgrade plan for 'rabbitmq-server' to victoria ✔

    Upgrade plan for 'keystone' to victoria
            Upgrade software packages of 'keystone' from the current APT repositories
            Upgrade 'keystone' to the new channel: 'victoria/stable'
            Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
            Wait 1800s for model test-model to reach the idle state.
            Check if the workload of 'keystone' has been upgraded

    Continue (y/n): y
    Upgrade software packages of 'keystone' from the current APT repositories \

    ...  # apply each step
    Upgrade completed.


Run non-interactive upgrades
----------------------------

**COU** provides a non-interactive mode which suppresses user prompts. This option
allows **COU** to be used by scripts or during upgrade testing. A quiet mode switch
is also offered, which will only output error logs and a completion message to STDOUT.

Usage examples
^^^^^^^^^^^^^^

Non-interactive mode:

.. code:: 

    $ cou upgrade --no-interactive
    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    ...
    Running cloud upgrade...
    Verify that all OpenStack applications are in idle state ✔
    Backup mysql databases ✔
    Upgrade software packages of 'keystone' from the current APT repositories ✔
    Upgrade 'keystone' to the new channel: 'victoria/stable' ✔
    ...
    Upgrade completed.


Non-interactive and quiet mode:

.. code:: 

    $ cou upgrade --no-interactive --quiet
    Upgrade completed.