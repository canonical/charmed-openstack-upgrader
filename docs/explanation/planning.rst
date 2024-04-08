========
Planning
========

The plan has a tree structure with six main sections:

* cloud pre-upgrade steps,
* control-plane principal applications upgrade
* control-plane subordinate applications upgrade
* data-plane hypervisors upgrade
* data-plane non-hypervisor principal applications upgrade
* data-plane subordinate applications upgrade
* cloud post-upgrade steps.

.. code:: text

    Upgrade cloud from current release to target release
        cloud pre-upgrade steps
            Verify cloud is in idle state
            MySQL backup
        control-plane principal applications upgrade
                application 1
                    pre-upgrade steps
                    upgrade steps
                    post-upgrade steps
                ...
                application N
                    ...
        control-plane subordinate applications upgrade
                application M
                    ...
        data-plane hypervisors upgrade
                availability zone 1
                    pre-upgrade steps
                    upgrade steps
                        unit 1
                            unit upgrade steps
                        ...
                        unit K
                            unit upgrade steps
                    post-upgrade steps
                ...
                availability zone N
                    ...
        data-plane non-hypervisor principal applications upgrade
                application P
                    ...
        data-plane subordinate applications upgrade
                application Q
                    ...
        cloud post-upgrade steps
            (if ceph exists) Ensure correctness of 'require-osd-release' option in 'ceph-mon'
    ...

The **pre-upgrade** steps prepare COU for the upgrade process, which includes
verifying the states or configurations of the applications, units, or of the
OpenStack cloud.

The **upgrade** steps are the main steps needed to run upgrades for each application.

The **post-upgrade** steps are responsible for making sure that the upgrade finishes
successfully.

The plan can also be obtained without the need to perform a cloud upgrade using
the **plan** command. See :doc:`Plan an upgrade <../how-to/plan-upgrade>`.

Different upgrade strategies are chosen for control-plane and data-plane applications
when preparing the plan. For details, please refer to :doc:`Upgrade <./upgrade>`.