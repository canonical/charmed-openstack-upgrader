======================================
Target a different model or controller
======================================

The current active model will be used by default, but it's possible to select a
different one, even on a different controller. There are two ways to choose the
model you want to operate on.

Using CLI argument
------------------

.. code:: bash

    cou plan --model <model-name>
    cou plan --model <controller>:<model-name>

Using environment variables
---------------------------

Since **COU** is using `python-libjuju`_, it's possible for some of the environment variables
mentioned in the documented `Juju environment variables`_ to affect the behaviour of the
program. For example, `JUJU_DATA`_ can be used to specify a different path for Juju
configuration files.

.. code:: bash

    JUJU_DATA=./my-remote-cloud-juju-data cou plan


.. LINKS
.. _python-libjuju: https://github.com/juju/python-libjuju
.. _Juju environment variables: https://juju.is/docs/juju/environment-variables#heading--jujudata
.. _JUJU_DATA: https://juju.is/docs/juju/environment-variables#heading--jujudata
