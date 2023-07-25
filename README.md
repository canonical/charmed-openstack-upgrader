# DISCLAIMER
This is a work in progress prototype. The code contained in this repository
may not be representative of what the final approach should be.
It is likely that the end result will live under a different name, in a
different repository, and only use some of the code and ideas found here.


Setup
-

```bash
rm *.snap
snapcraft clean
sudo snap remove charmed-openstack-upgrader --purge
make build
sudo snap install ./charmed-openstack-upgrader.snap --devmode
sudo snap connect charmed-openstack-upgrader:juju-client-observe snapd
sudo snap connect charmed-openstack-upgrader:dot-local-share-juju snapd
sudo snap connect charmed-openstack-upgrader:local-cou snapd
```


Then you can use ```cou```
