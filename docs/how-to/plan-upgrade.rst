================
Plan an upgrade
================

The **plan** command is used to generate the upgrade plan; the result will be
printed on STDOUT.

.. code:: bash

    cou plan

Usage example
-------------

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
        Upgrade plan for 'rabbitmq-server' to 'victoria'
            Upgrade software packages of 'rabbitmq-server' from the current APT repositories
                Upgrade software packages on unit rabbitmq-server/0
                Upgrade software packages on unit rabbitmq-server/1
                Upgrade software packages on unit rabbitmq-server/2
            Upgrade 'rabbitmq-server' to the new channel: '3.9/stable'
            Change charm config of 'rabbitmq-server' 'source' to 'cloud:focal-victoria'
            Wait for up to 1800s for model 'test-model' to reach the idle state
            Verify that the workload of 'rabbitmq-server' has been upgraded
        Upgrade plan for 'keystone' to 'victoria'
            Upgrade software packages of 'keystone' from the current APT repositories
                Upgrade software packages on unit keystone/0
                Upgrade software packages on unit keystone/1
                Upgrade software packages on unit keystone/2
            Upgrade 'keystone' to the new channel: 'victoria/stable'
            Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 1800s for model 'test-model' to reach the idle state
            Verify that the workload of 'keystone' has been upgraded
        Upgrade plan for 'cinder' to 'victoria'
            Upgrade software packages of 'cinder' from the current APT repositories
                Upgrade software packages on unit cinder/0
            Upgrade 'cinder' to the new channel: 'victoria/stable'
            Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Verify that the workload of 'cinder' has been upgraded
        Upgrade plan for 'glance' to 'victoria'
            Upgrade software packages of 'glance' from the current APT repositories
                Upgrade software packages on unit glance/0
            Upgrade 'glance' to the new channel: 'victoria/stable'
            Change charm config of 'glance' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 300s for app 'glance' to reach the idle state
            Verify that the workload of 'glance' has been upgraded
        Upgrade plan for 'neutron-api' to 'victoria'
            Upgrade software packages of 'neutron-api' from the current APT repositories
                Upgrade software packages on unit neutron-api/0
            Upgrade 'neutron-api' to the new channel: 'victoria/stable'
            Change charm config of 'neutron-api' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 300s for app 'neutron-api' to reach the idle state
            Verify that the workload of 'neutron-api' has been upgraded
        Upgrade plan for 'neutron-gateway' to 'victoria'
            Upgrade software packages of 'neutron-gateway' from the current APT repositories
                Upgrade software packages on unit neutron-gateway/0
            Upgrade 'neutron-gateway' to the new channel: 'victoria/stable'
            Change charm config of 'neutron-gateway' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 300s for app 'neutron-gateway' to reach the idle state
            Verify that the workload of 'neutron-gateway' has been upgraded
        Upgrade plan for 'placement' to 'victoria'
            Upgrade software packages of 'placement' from the current APT repositories
                Upgrade software packages on unit placement/0
            Upgrade 'placement' to the new channel: 'victoria/stable'
            Change charm config of 'placement' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 300s for app 'placement' to reach the idle state
            Verify that the workload of 'placement' has been upgraded
        Upgrade plan for 'nova-cloud-controller' to 'victoria'
            Upgrade software packages of 'nova-cloud-controller' from the current APT repositories
                Upgrade software packages on unit nova-cloud-controller/0
            Upgrade 'nova-cloud-controller' to the new channel: 'victoria/stable'
            Change charm config of 'nova-cloud-controller' 'openstack-origin' to 'cloud:focal-victoria'
            Wait for up to 300s for app 'nova-cloud-controller' to reach the idle state
            Verify that the workload of 'nova-cloud-controller' has been upgraded
        Upgrade plan for 'mysql' to 'victoria'
            Upgrade software packages of 'mysql' from the current APT repositories
                Upgrade software packages on unit mysql/0
            Change charm config of 'mysql' 'source' to 'cloud:focal-victoria'
            Wait for up to 1800s for app 'mysql' to reach the idle state
            Verify that the workload of 'mysql' has been upgraded
        Control Plane subordinate(s) upgrade plan
        Upgrade plan for 'neutron-openvswitch' to 'victoria'
            Upgrade 'neutron-openvswitch' to the new channel: 'victoria/stable'
