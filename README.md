# DISCLAIMER

This is a work in progress prototype. The code contained in this repository
may not be representative of what the final approach should be.
It is likely that the end result will live under a different name, in a
different repository, and only use some of the code and ideas found here.

# Setup

```bash
# Instructions for local builds until we have automatic connections and alias
make clean
sudo snap remove charmed-openstack-upgrader --purge
make build
sudo snap install ./charmed-openstack-upgrader.snap --dangerous
sudo snap connect charmed-openstack-upgrader:juju-client-observe snapd
sudo snap connect charmed-openstack-upgrader:dot-local-share-cou snapd
sudo snap alias charmed-openstack-upgrader.cou cou
```

Then you can use ```cou```

## Environment Variables

- `COU_DATA`: Main directory for Charmed Openstack Upgrader configuration files. Currently only log files are kept under
  COU_DATA/logs.
- `JUJU_MODEL`: Active juju model to operate on.

## Supported Upgrade Paths

Application supports:

- Focal/Ussuri -> Focal/Victoria
- Focal/Victoria -> Focal/Xena
- Focal/Xena -> Focal/Wallaby
- Focal/Wallaby -> Focal/Yoga

upgrades.
