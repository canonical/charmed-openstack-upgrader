==========================================
Run upgrades without cloud database backup
==========================================

By default, COU makes a backup of the cloud database before proceeding to actual
upgrade steps. This can be turned off with `--no-backup`  flag.

Usage example
~~~~~~~~~~~~~

.. code:: 

    $ cou plan --no-backup
    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        # note that there's no backup step planned
        Control Plane principal(s) upgrade plan
        Upgrade plan for 'rabbitmq-server' to victoria
            Upgrade software packages of 'rabbitmq-server' from the current APT repositories
        …
