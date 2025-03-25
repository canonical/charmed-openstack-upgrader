========
Security
========

Charmed OpenStack Upgrader orchestrates upgrade operations on a cloud by leveraging the
Juju client and automating the actions a human operator would perform. It does not by
itself perform any cryptographic operation, although it relies on libjuju for
communicating securely with the Juju controller and performing lower level secure
operations like ssh or scp.

Having a juju snap installed and configured to connect to the desired controller is a
prerequisite for using Charmed OpenStack Upgrader.

Please refer to `Juju's documentation`_ for more details.

.. LINKS:
.. _Juju's documentation:  https://documentation.ubuntu.com/juju/latest/user/reference/juju-cli/juju-environment-variables/
