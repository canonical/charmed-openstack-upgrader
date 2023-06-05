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

sudo snap alias charmed-openstack-upgrader.cou cou
```


Then you can use ```cou```
