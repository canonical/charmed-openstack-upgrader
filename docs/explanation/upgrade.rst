=======
Upgrade
=======

This phase is responsible for applying the upgrade plan step by step (See
:doc:`Upgrade a cloud <../how-to/upgrade-cloud>`). By default steps are applied
sequentially, but there are steps which can be run in parallel.

Required Juju commands
~~~~~~~~~~~~~~~~~~~~~~

Any upgrade step may require different Juju commands, from changing configuration
to running commands directly on a unit.
