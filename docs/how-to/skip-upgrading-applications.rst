==========================================
Plan/Upgrade without some applications
==========================================

.. Warning::

    Skipping the upgrade for some applications might result in the cloud being
    broken. You are strongly encouraged to verify if the applications you want
    to skip will still be compatible with the cloud after the cloud is
    upgraded.

.. Note::

    This feature currently only supports vault.

By default, COU plan and upgrade will generate upgrade plan and run the upgrade
for all the applications supported by COU. However, it is possible that some
applications in the existing deployment can be in the unsupported version for
COU, and COU will not perform the upgrade unless the operator adjust the
deployment until it meets the version requirement. Often time, due to technical
reasons, adjusting the application version on production environment is not
desired. COU offers the --skip-apps to allow the operator to skip upgrading
applications that are known to be safe.

Usage examples
--------------

Plan without vault.

.. code:: bash

    cou plan --skip-apps vault

Upgrade without vault.

.. code:: bash

    cou upgrade --skip-apps vault
