===============
Using Landscape
===============

In air-gapped environments, users can still leverage COU to perform OpenStack upgrades by
configuring the **LANDSCAPE_MIRROR_URI** and **LANDSCAPE_APT_COMPONENT** variables to point to an
internal APT mirror. COU automatically detects the currently deployed OpenStack release and
derives the appropriate Ubuntu Cloud Archive pocket (e.g., focal-ussuri), ensuring compatibility
between the Ubuntu release and OpenStack version. Based on this detection, COU populates the
relevant charm configuration fields such as **openstack-origin** or **source** with the correct
repository entry—for example, **deb http://example.com focal-ussuri main**—allowing the upgrade
process to proceed without requiring external network access.
