Charmed OpenStack Upgrader
==========================

`Charmed OpenStack Upgrader`_ (**COU**) is an application (packaged as a snap) to upgrade
a Canonical distribution of `Charmed OpenStack`_
in an automated and frictionless manner. The application detects the version of the
running cloud and proposes an upgrade plan to the next available OpenStack release.

**COU** follows the steps defined in the `charm-guide`_ upgrades overview, and
it supports the upgrades for the following OpenStack releases:

==============  ==============
From            To
==============  ==============
Focal/Ussuri    Focal/Victoria
Focal/Victoria  Focal/Wallaby
Focal/Wallaby   Focal/Xena
Focal/Xena      Focal/Yoga
Jammy/Yoga      Jammy/Zed
Jammy/Zed       Jammy/Antelope
Jammy/Antelope  Jammy/Bobcat
Jammy/Bobcat    Jammy/Caracal
==============  ==============

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

      **Technical information** - commands, environmental variables, and known issues

   .. grid-item:: :doc:`Explanation <explanation/index>`

      **Additional information** - details of upgrade phases and scopes defined in **COU**

---------

Project and community
---------------------

COU is a member of the Ubuntu family. It's an open source project that
warmly welcomes community contributions, suggestions, fixes and
constructive feedback.

* We follow the Ubuntu community `Code of conduct`_
* Contribute to the project on `GitHub`_ (documentation contributions go under
  the **docs/** directory)
* GitHub is also our central hub for bug tracking and issue management

.. toctree::
   :hidden:
   :maxdepth: 2

   get-started/index
   how-to/index
   reference/index
   explanation/index

.. LINKS
.. _Charmed OpenStack Upgrader: https://snapcraft.io/charmed-openstack-upgrader
.. _Charmed OpenStack: https://ubuntu.com/openstack/docs
.. _charm-guide: https://docs.openstack.org/charm-guide/latest/admin/upgrades/overview.html
.. _Code of conduct: https://ubuntu.com/community/ethos/code-of-conduct
.. _GitHub: https://github.com/canonical/charmed-openstack-upgrader
