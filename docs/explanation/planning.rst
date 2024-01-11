========
Planning
========

The plan has a tree structure with three main sections: pre-upgrade steps,
control-plane upgrade and data-plane upgrade.

.. code:: 

    Top-level plan
    ├── pre-upgrade steps
    │   ├── verify cloud is in idle state
    │   └── MySQL backup
    ├── control-plane upgrade
    │   ├── principal applications
    │   |   ├── application 1..
    │   |   |   ├── pre-upgrade steps
    |   |   |   ├── upgrade steps
    │   |   |   └── post-upgrade steps
    │   |   └── application N
    │   |       ├── pre-upgrade steps
    |   |       ├── upgrade steps
    │   |       └── post-upgrade steps
    |   └── subordinate applications...
    ├── data-plane upgrade
    ...

The **pre-upgrades** steps are used to obtain any further information about the
applications or to verify their state. 

The **upgrade** steps are the main steps needed to run upgrades for each application.

The **post-upgrade** steps are responsible for making sure that upgrade finishes
successfully. 

The plan can also be obtained without the need to perform cloud upgrade using
the **plan** command. See :doc:`Plan an upgrade <../how-to/plan-upgrade>`.
