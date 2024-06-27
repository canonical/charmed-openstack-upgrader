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
(`openstack_lookup.csv` and `openstack_to_track_mapping.csv`) for generating
upgrade paths.

When you are changing the upgrade paths, make sure to review the external
official websites for the following constants:

- `OPENSTACK_CODENAMES` [1][1]
- `DISTRO_TO_OPENSTACK_MAPPING` [2][2]
- `LTS_TO_OS_RELEASE` [1][1],[3][3],[5][5]
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

The version of some packages cannot be found directly from the official release
pages (often they non-OpenStack packages). In this situation, the version can be
obtained from the debian package itself using `cmadison` or `rmadison`. For
example, the `workload_version` for charm `designate-bind` tracks the version of
the debian package `bind9`, and we can use `rmadison bind9` to find all the
versions for charm `designate-bind`. Similarly, for charm `gnocchi`, the
versions can be found using `cmadison gnocchi`.

**Note**: Generally, the `upper_version` of the last release is unknown, we can increase
the "PATCH" number of `lower_version` by one, to set the `upper_version`. This
way, it's effectively making the `lower_version` is the only compatible version
for the last release. However, we will need to revisit this column frequently to
ensure the information is up-to-date.

## `openstack_to_track_mapping.csv`

This file defines the track mappings for the auxiliary charms, and it should be
updated periodically by adding new lines to the file.

The csv table is made from [charm delivery][5], using the "Tracks for the
OpenStack Charms project" table. The `series` column is the Ubuntu series, the
`o7k_release` column is the [OpenStack release identifier][1] corresponding to
auxiliary charms, and the `track` column is the track for the auxiliary charms
on charmhub.

**Note**: The `o7k_release` must match the `LTS_TO_OS_RELEASE` in the
`cou/utils/openstack.py`, and they should be the *codename* of the OpenStack
release (e.g. `zed`, `antelope`).

**Note**: Starting from OpenStack Antelope, the OpenStack release identifier
will use *release date* instead of *release codename*.


[1]: https://governance.openstack.org/tc/reference/release-naming.html
[2]: https://ubuntu.com/about/release-cycle#ubuntu
[3]: https://ubuntu.com/openstack/docs/supported-versions
[5]: https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html#tracks-for-the-openstack-charms-project
[6]: https://docs.ceph.com/en/latest/releases/
[7]: https://releases.openstack.org/
