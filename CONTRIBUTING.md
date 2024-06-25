# Contributing to Charmed OpenStack Upgrader (COU)

Thank you for your interest in helping us improve **COU**! We're open to
community contributions, suggestions, fixes, and feedback. This documentation
will assist you in navigating through our processes.

Make sure to review this guide thoroughly before beginning your contribution. It
provides all the necessary details to increase the likelihood of your contribution
being accepted.

COU is hosted and managed on [GitHub](https://github.com). If you're new to GitHub
and not familiar with how it works, their
[quickstart documentation](https://docs.github.com/en/get-started/quickstart)
provides an excellent introduction to all the tools and processes you'll need
to know.

## Prerequisites

Before you can begin, you will need to:

* Read and agree to abide by our
  [Code of Conduct](https://ubuntu.com/community/code-of-conduct).

* Sign the Canonical
  [contributor license agreement](https://ubuntu.com/legal/contributors). This
  grants us your permission to use your contributions in the project.

* Create (or have) a GitHub account.

* If you're working in a local environment, it's important to create a signing
  key, typically using GPG or SSH, and register it in your GitHub account to
  verify the origin of your code changes. For instructions on setting this up,
  please refer to
  [Managing commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification).

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

## Find issues to work on
[GitHub Issues](https://github.com/canonical/charmed-openstack-upgrader/issues)
is our central hub for bug tracking and issue management, with labels used to
organize them into different categories. For new contributors, we recommend
starting with issues labeled "good first issue." If you're interested in
enhancing our documentation, you can filter issues using the "documentation"
label to find issues specifically related to documentation improvement.

Once you have decided which issue to work on, you can express your interest by
posting a comment on it. When you submit your proposed fix for an issue, link
your PR to the issue with one of the supported
[keywords](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue#linking-a-pull-request-to-an-issue-using-a-keyword).

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

Installing a local snap has some manual steps because it must be installed in 'dangerous' mode:

```
make build
sudo snap install --dangerous ./charmed-openstack-upgrader.snap
sudo snap alias charmed-openstack-upgrader.cou cou
sudo snap connect charmed-openstack-upgrader:juju-client-observe
sudo snap connect charmed-openstack-upgrader:dot-local-share-cou
sudo snap connect charmed-openstack-upgrader:ssh-public-keys
```
