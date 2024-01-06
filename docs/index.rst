Charmed OpenStack Upgrader
==========================

`Charmed OpenStack Upgrader`_ (COU) is an application (packaged as a snap) to upgrade
a Canonical distribution of `Charmed OpenStack`_
in an automated and frictionless manner. The application detects the version of the
running cloud and proposes an upgrade plan to the next available OpenStack release.

COU follows the steps defined in the `charm-guide`_ upgrades overview.

Notes:

- Currently only control plane upgrades are supported.

- The tool supports upgrades from focal-ussuri to focal-yoga.

Source code available on `Github`_.

In this documentation
---------------------

..  grid:: 1 1 2 2

   ..  grid-item:: :doc:`Get Started <get-started/index>`

      **Start here** to prepare the environment and install the application

   ..  grid-item:: :doc:`How-to guides <how-to/index>`

      **Step-by-step guides** covering key operations and common tasks

.. grid:: 1 1 2 2

   .. grid-item:: :doc:`Reference <reference/index>`

      **Technical information** - available commands and environmental variables
   
   .. grid-item:: :doc:`Explanation <explanation/index>`

      **Additional information** - details of upgrade phases and known issues


.. toctree::
   :hidden:
   :maxdepth: 2

   get-started/index
   how-to/index
   reference/index
   explanation/index

.. LINKS
.. _Charmed OpenStack Upgrader: https://snapcraft.io/charmed-openstack-upgrader
.. _Charmed OpenStack: https://ubuntu.com/openstack/docs/overview
.. _charm-guide: https://docs.openstack.org/charm-guide/latest/admin/upgrades/overview.html
.. _Code of conduct: https://ubuntu.com/community/ethos/code-of-conduct
.. _GitHub: https://github.com/canonical/charmed-openstack-upgrader
