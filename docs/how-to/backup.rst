===============
Backup database
===============

By default, **COU** plans for and runs a backup step of the cloud database before
proceeding to actual upgrade steps.

Find mysql backup file
~~~~~~~~~~~~~~~~~~~~~~

The file is store under ``$COU_DATA``, which is ``/home/$USER/.local/share/cou`` if ``$USER`` exists else current directory.


Plan/Upgrade without cloud database backup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To plan/upgrade without backup, this can be turned off with ``--no-backup`` flag.

Usage examples
^^^^^^^^^^^^^^


Plan:

.. terminal::
    :input: cou plan --no-backup

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    Upgrade cloud from 'ussuri' to 'victoria'
        Verify that all OpenStack applications are in idle state
        # note that there's no backup step planned
        Archive old database data on nova-cloud-controller
        Control Plane principal(s) upgrade plan
        Upgrade plan for 'rabbitmq-server' to 'victoria'
            Upgrade software packages of 'rabbitmq-server' from the current APT repositories
                Upgrade software packages on unit 'rabbitmq-server/0'
                Upgrade software packages on unit 'rabbitmq-server/1'
                Upgrade software packages on unit 'rabbitmq-server/2'
        ...

Upgrade:

.. terminal::
    :input: cou upgrade --no-backup

    Full execution log: '/home/ubuntu/.local/share/cou/log/cou-20231215211717.log'
    Connected to 'test-model' ✔
    Analyzing cloud... ✔
    Generating upgrade plan... ✔
    ...
    Running cloud upgrade...
    Verify that all OpenStack applications are in idle state ✔
    # note that there's no backup step being executed

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

    ... # apply steps
    Upgrade completed.
