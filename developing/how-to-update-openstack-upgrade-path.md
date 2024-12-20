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

The list of packages need to be updated are:

```shell
# Install rmadison
apt install devscripts
# Install cmadison
snap install cmadison

# For the following packages, guess an appropriate upper version for the
specific release from the list
rmadison gnocchi
rmadison bind9
rmadison rabbitmq-server

# For example, the upper version for rabbitmq-server in Jammy/2023.2 (Bobcat) is
# 3.9.27, an educated guess for the upper version will be 3.10.

root@enabling-stallion:~# rmadison rabbitmq-server
 rabbitmq-server | 3.2.4-1                      | trusty           | source, all
 rabbitmq-server | 3.2.4-1ubuntu0.1             | trusty-security  | source, all
 rabbitmq-server | 3.2.4-1ubuntu0.1             | trusty-updates   | source, all
 rabbitmq-server | 3.5.7-1                      | xenial           | source, all
 rabbitmq-server | 3.5.7-1ubuntu0.16.04.2       | xenial-security  | source, all
 rabbitmq-server | 3.5.7-1ubuntu0.16.04.4       | xenial-updates   | source, all
 rabbitmq-server | 3.6.10-1                     | bionic           | source, all
 rabbitmq-server | 3.6.10-1ubuntu0.5            | bionic-security  | source, all
 rabbitmq-server | 3.6.10-1ubuntu0.5            | bionic-updates   | source, all
 rabbitmq-server | 3.8.2-0ubuntu1~ubuntu18.04.1 | bionic-backports | source, all
 rabbitmq-server | 3.8.2-0ubuntu1               | focal            | source, all
 rabbitmq-server | 3.8.2-0ubuntu1.5             | focal-security   | source, all
 rabbitmq-server | 3.8.2-0ubuntu1.5             | focal-updates    | source, all
 rabbitmq-server | 3.8.3-0ubuntu0.1             | focal-proposed   | source, all
 rabbitmq-server | 3.9.13-1                     | jammy            | source, all
 rabbitmq-server | 3.9.13-1ubuntu0.22.04.2      | jammy-security   | source, all
 rabbitmq-server | 3.9.13-1ubuntu0.22.04.2      | jammy-updates    | source, all
 rabbitmq-server | 3.9.27-0ubuntu0.1            | jammy-proposed   | source, all
 rabbitmq-server | 3.12.1-1ubuntu1              | noble            | source, all
 rabbitmq-server | 3.12.1-1ubuntu1.1            | noble-proposed   | source, all
 rabbitmq-server | 3.12.1-1ubuntu2              | oracular         | source, all
 rabbitmq-server | 3.12.1-1ubuntu2              | plucky           | source, all
```

For the following packages, the upper version can be found found in [charm
delivery][5]
- mysql
- vault
- ovn

For `ceph` packages, the upper version can be found found in [ceph release
page][6]
- ceph

The rest of the openstack components are found in [release page][7]

**Note**: Generally, the `upper_version` of the last release is unknown, we
should use educated guess to set the `upper_version` (e.g. based on the past
experience), and create an github issue to track the issue in the future.

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
