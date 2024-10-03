# Charmed OpenStack Upgrader

Charmed OpenStack Upgrader (COU) is an application (packaged as a snap) to upgrade
a Canonical distribution of [Charmed OpenStack](https://ubuntu.com/openstack/docs/overview)
in an automated and frictionless manner. The application detects the version of the
running cloud and proposes an upgrade plan to the next available OpenStack release.

For more information, please refer to [COU Documentation](https://canonical-charmed-openstack-upgrader.readthedocs-hosted.com/).

# Setup

The Charmed OpenStack Upgrader snap can be installed directly from the snap store:

```bash
sudo snap install charmed-openstack-upgrader
```

An alias `cou` will be automatically enabled upon successful installation.

Run `cou -h` to learn about the available commands:

```bash
Usage: cou [options] <command>

Charmed OpenStack Upgrader (cou) is an application to upgrade
a Canonical distribution of Charmed OpenStack.
The application auto-detects the version of the running cloud
and will propose an upgrade to the next available version.

Options:
  -h, --help           Show this help message and exit.
  --version, -V        Show version details.

Commands:
  {help,plan,upgrade}  For more information about a command, run 'cou help <command>'.
    plan               Show the steps COU will take to upgrade the cloud to the next release.
    upgrade            Run the cloud upgrade.
```

## Environment Variables

- `JUJU_DATA` - sets the path containing Juju configuration files (e.g. credentials.yaml). Defaults to ~/.local/share/juju
- `COU_TIMEOUT` - define timeout for cou retry policy. Default value is 10 seconds.
- `COU_MODEL_RETRIES` - define how many times to retry the connection to Juju model before giving up. Default value is 5 times.
- `COU_MODEL_RETRY_BACKOFF` - define number of seconds to increase the wait between connection to the Juju model retry attempts. Default value is 2 seconds.
- `COU_STANDARD_IDLE_TIMEOUT` - how long COU will wait for an application to settle to active/idle and declare the upgrade complete. The default value is 300 seconds.
- `COU_LONG_IDLE_TIMEOUT` - a longer version of COU_STANDARD_IDLE_TIMEOUT for applications that are known to need more time than usual to upgrade like such as Keystone and Octavia. The default value is 2400 seconds.

## Supported Upgrade Paths

Application supports:

| From           | To             |
| -------------- | -------------- |
| Focal/Ussuri   | Focal/Victoria |
| Focal/Victoria | Focal/Wallaby  |
| Focal/Wallaby  | Focal/Xena     |
| Focal/Xena     | Focal/Yoga     |
| Jammy/Yoga     | Jammy/Zed      |
| Jammy/Zed      | Jammy/Antelope |
| Jammy/Antelope | Jammy/Bobcat   |
| Jammy/Bobcat   | Jammy/Caracal  |

# License
Charmed OpenStack Upgrader is a free software, distributed under the Apache-2.0 license. Refer to the
[LICENSE](https://github.com/canonical/snap-tempest/blob/main/LICENSE) file for details.
