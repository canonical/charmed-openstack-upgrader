# Charmed OpenStack Upgrader (COU) Development notes

## Code contribution
If you're interested in making code contributions, please begin by forking the
repository to your own GitHub account. From there, you can open Pull Requests (PRs)
against the `main` branch of the upstream repository.

Please adhere to the following guidelines prior to submitting your changes:

- Add or update any unit tests accordingly if applicable.
- Format code with `make reformat` (which runs `black` and `isort`)
- Ensure unit tests and/or linting checks pass by running `make lint` and
  `make unittests`
  - For documentation contribution, run the following commands and confirm that
  - no errors are raised:
    ```bash
    cd docs/
    make clean
    make html
    make spelling
    make woke
    make linkcheck
    ```
- Commit messages should be well-structured and provide a meaningful explanation
  of the changes made
- Commits must be signed (refer to the [Prerequisites](#prerequisites) section)

## Add new or update OpenStack upgrade paths
COU relies on external documentation to define the OpenStack upgrade paths (e.g.
the version, charm tracks, and Ubuntu base). The external documatation may not
align with the development and release cycle of this project, so the information
in COU may be out-of-date. You can follow this [document](./developing/how-to-update-openstack-upgrade-path.md)
to learn how to update the OpenStack upgrade paths.

## Development environment

To set up a development environment to run from source,
you can install it in a virtual environment,
for example:

```
virtualenv venv
source venv/bin/activate
pip install -e .

# run cou!
cou --version
```

## Testing the snap

Installing a local snap has some manual steps,
because aliases are not automatically setup,
and interfaces that normally require approval are not automatically connected.

```
make build
sudo snap install --dangerous ./charmed-openstack-upgrader.snap
sudo snap alias charmed-openstack-upgrader.cou cou
sudo snap connect charmed-openstack-upgrader:juju-client-observe
sudo snap connect charmed-openstack-upgrader:dot-local-share-cou
sudo snap connect charmed-openstack-upgrader:ssh-public-keys
```
