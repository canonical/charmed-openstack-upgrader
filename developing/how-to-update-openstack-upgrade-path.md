# OpenStack Upgrade Paths

The OpenStack upgrade paths in Charmed OpenStack Upgrader (COU) is defined by
the following files:

- `cou/utils/openstack.py`
- `cou/utils/openstack_lookup.csv`
- `cou/utils/openstack_to_track_mapping.csv`

Whenever you want to update or add new upgrade paths, you should go through
these files, and make changes to the relevant places.

## `cou/utils/openstack.py`

This file contains some constants such as the list of OpenStack charms,
OpenStack release name, and Ceph release name for defining the supported
OpenStack releases. It also dynamically loads the content of the csv files
(`openstack_lookup.csv` and `openstack_to_track_mapping.csv`) for generating a
upgrade paths.

When you are changing the upgrade paths, make sure to review the external
official website the for the following constants:

- `OPENSTACK_CODENAMES` [1][1]
- `DISTRO_TO_OPENSTACK_MAPPING` [2][2]
- `LTS_TO_OS_RELEASE` [3][3],[4][4],[5][5]
- `CEPH_RELEASES` [6][6]

## `cou/utils/openstack_lookup.csv`

This file defines an OpenStack lookup dictionary based on the version of the
components.

The information should be updated regularly to include new OpenStack releases and
updates to the lower and upper versions of the services. The csv table is made
from the [charm delivery][5], [ceph release page][6], [release page][7],
`cmadison` and `rmadison`. The lower version is the lowest version of a certain
release (N) while the upper is the first incompatible version.  This way, new
patches won't affect the comparison.

Charm designate-bind workload_version tracks the version of the deb package
bind9. For charm gnocchi it was used `cmadison`.

**Note**: Generally, the `upper_version` of the last release is unknown, we can increase
the "PATCH" number of `lower_version` by one, to set the `upper_version`. This
way, it's effectively making the `lower_version` is the only compatible version
for the last release. However, we will need to revisit this column frequently to
ensure the information is up-to-date.

## `cou/utils/openstack_lookup.csv`

This file defines the track mappings for the auxiliary charms, and it should be
updated periodically by adding new lines to the file.

The csv table is made from the [charm delivery][5].


[1]: https://governance.openstack.org/tc/reference/release-naming.html
[2]: https://ubuntu.com/about/release-cycle#ubuntu
[3]: https://ubuntu.com/openstack/docs/supported-versions
[4]: https://governance.openstack.org/tc/reference/release-naming.html
[5]: https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html
[6]: https://docs.ceph.com/en/latest/releases/
[7]: https://releases.openstack.org/
