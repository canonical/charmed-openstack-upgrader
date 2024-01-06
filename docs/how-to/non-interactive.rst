============================
Run non-interactive upgrades
============================

COU provides a non-interactive mode which suppresses user prompts. This option
allows cou to be used by scripts or during upgrade testing. A quiet mode switch
is also offered, which will only output error logs and a completion message to STDOUT.

Usage examples
~~~~~~~~~~~~~~

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