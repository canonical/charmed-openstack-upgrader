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
sudo snap connect charmed-openstack-upgrader:ssh-public-keys snapd
sudo snap alias charmed-openstack-upgrader.cou cou
```

Then you can use ```cou```

## Environment Variables

- `JUJU_DATA` - sets the path containing Juju configuration files (e.g. credentials.yaml). Defaults to ~/.local/share/juju
- `COU_TIMEOUT` - define timeout for cou retry policy. Default value is 10 seconds.
- `COU_MODEL_RETRIES` - define how many times to retry the connection to Juju model before giving up. Default value is 5 times.
- `COU_MODEL_RETRY_BACKOFF` - define number of seconds to increase the wait between connection to the Juju model retry attempts. Default value is 2 seconds.

## Supported Upgrade Paths

Application supports:

- Focal/Ussuri -> Focal/Victoria
- Focal/Victoria -> Focal/Xena
- Focal/Xena -> Focal/Wallaby
- Focal/Wallaby -> Focal/Yoga

upgrades.
