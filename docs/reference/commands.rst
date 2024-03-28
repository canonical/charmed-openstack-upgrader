========
Commands
========

**COU** offers only two commands; bash completion further simplifies its usage.

Plan
----

The **plan** command will analyse the cloud and output a human-readable representation
of the proposed upgrade plan. It does not require any interaction. Refer to the
output below for a description of all allowed options.

.. terminal:: 
    :input: cou plan --help

    Usage: cou plan [options]

    Show the steps COU will take to upgrade the cloud to the next release.
    If upgrade-group is unspecified, plan upgrade for the whole cloud.

    Options:
      -h, --help            Show this help message and exit.
      --model MODEL_NAME    Set the model to operate on.
                            If not set, the currently active Juju model will be used.
      --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
      --force               Force the plan/upgrade of non-empty hypervisors.
      --verbose, -v         Increase logging verbosity in STDOUT.
                            Multiple 'v's yield progressively more detail (up to 3).
                            Note that by default the logfile will not include standard logs
                            from juju and websockets, as well as debug logs from all other
                            modules. To also include the debug level logs from juju and
                            websockets modules, use the maximum verbosity.
      --quiet, -q           Disable output in STDOUT.

    Upgrade groups:
      {control-plane,data-plane,hypervisors}
                            Run 'cou plan <upgrade-group> -h' for more info about an upgrade group.
        control-plane       Show the steps for upgrading the control-plane components.
        data-plane          Show the steps for upgrading all data-plane components.
                            This is possible only if control-plane has been fully upgraded,
                            otherwise an error will be thrown.
        hypervisors         Show the steps for upgrading machines with nova-compute and
                            colocated services. This is possible only if control-plane
                            has been fully upgraded, otherwise an error will be thrown.

By default, COU plans upgrade for the entire OpenStack cloud with `cou plan`. However, the
upgrade process can be tailored to target a specific group through a sub-command for more
granular control. For further details, please see the `Upgrade Groups`_ section.

Upgrade
-------

The **upgrade** command will implicitly generate a plan before moving onto the actual
upgrade phase. Refer to the output below for a description of all available options. 

.. terminal:: 
    :input: cou upgrade --help
    
    Usage: cou upgrade [options]

    Run the cloud upgrade.
    If upgrade-group is unspecified, upgrade the whole cloud.

    Options:
      -h, --help            Show this help message and exit.
      --model MODEL_NAME    Set the model to operate on.
                            If not set, the currently active Juju model will be used.
      --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
      --force               Force the plan/upgrade of non-empty hypervisors.
      --verbose, -v         Increase logging verbosity in STDOUT.
                            Multiple 'v's yield progressively more detail (
                            
                            
                            
                            3).
                            Note that by default the logfile will not include standard logs
                            from juju and websockets, as well as debug logs from all other
                            modules. To also include the debug level logs from juju and
                            websockets modules, use the maximum verbosity.
      --quiet, -q           Disable output in STDOUT.
      --auto-approve        Automatically approve and continue with each upgrade step without prompt.

    Upgrade group:
      {control-plane,data-plane,hypervisors}
                            Run 'cou upgrade <upgrade-group> -h' for more info about an upgrade group
        control-plane       Run upgrade for the control-plane components.
        data-plane          Upgrade all data-plane components.
                            This is possible only if control-plane has been fully upgraded,
                            otherwise an error will be thrown.
        hypervisors         Upgrade machines with nova-compute and colocated services.
                            This is possible only if control-plane has been fully upgraded,
                            otherwise an error will be thrown.

By default COU upgrades the entire OpenStack cloud with `cou upgrade`. However, the upgrade
process can be tailored to target a specific group through a sub-command for more granular
control. For further details, please see the `Upgrade Groups`_ section.

Upgrade Groups
--------------

In COU, users can choose to selectively target only certain components in OpenStack cloud
for planning and executing upgrades, grouped by their roles. The available upgrade groups
are **control-plane**, **data-plane**, and **hypervisors**.

The options available for **control-plane** upgrade are:

.. terminal:: 
    :input: cou upgrade control-plane --help

    Usage: cou upgrade control-plane [options]

    Run upgrade for the control-plane components.

    Options:
      -h, --help            Show this help message and exit.
      --model MODEL_NAME    Set the model to operate on.
                            If not set, the currently active Juju model will be used.
      --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
      --force               Force the plan/upgrade of non-empty hypervisors.
      --verbose, -v         Increase logging verbosity in STDOUT.
                            Multiple 'v's yield progressively more detail (up to 3).
                            Note that by default the logfile will not include standard logs
                            from juju and websockets, as well as debug logs from all other
                            modules. To also include the debug level logs from juju and
                            websockets modules, use the maximum verbosity.
      --quiet, -q           Disable output in STDOUT.
      --auto-approve        Automatically approve and continue with each upgrade step without prompt.

The available options for a **data-plane** upgrade align closely with those offered for a
**control-plane** upgrade.

.. terminal:: 
    :input: cou upgrade data-plane --help

    Usage: cou upgrade data-plane [options]

    Upgrade all data-plane components.
    This is possible only if control-plane has been fully upgraded,
    otherwise an error will be thrown.

    Options:
      -h, --help            Show this help message and exit.
      --model MODEL_NAME    Set the model to operate on.
                            If not set, the currently active Juju model will be used.
      --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
      --force               Force the plan/upgrade of non-empty hypervisors.
      --verbose, -v         Increase logging verbosity in STDOUT.
                            Multiple 'v's yield progressively more detail (up to 3).
                            Note that by default the logfile will not include standard logs
                            from juju and websockets, as well as debug logs from all other
                            modules. To also include the debug level logs from juju and
                            websockets modules, use the maximum verbosity.
      --quiet, -q           Disable output in STDOUT.
      --auto-approve        Automatically approve and continue with each upgrade step without prompt.

For upgrading **hypervisors**, in addition to the common options also found in
**data-plane** upgrades, users can specify either **--machine** or **--az** to
narrow the upgrade to a particular subset of nodes.

.. terminal:: 
    :input: cou upgrade hypervisors --help

    Usage: cou upgrade hypervisors [options]

    Upgrade machines with nova-compute and colocated services.
    This is possible only if control-plane has been fully upgraded,
    otherwise an error will be thrown.

    Note that only principal applications colocated with nova-compute units
    that support action-managed upgrades are within the scope of this command.
    Other principal applications (e.g. ceph-osd) and subordinates
    can be upgraded via the data-plane subcommand.

    Options:
      -h, --help            Show this help message and exit.
      --model MODEL_NAME    Set the model to operate on.
                            If not set, the currently active Juju model will be used.
      --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
      --force               Force the plan/upgrade of non-empty hypervisors.
      --verbose, -v         Increase logging verbosity in STDOUT.
                            Multiple 'v's yield progressively more detail (up to 3).
                            Note that by default the logfile will not include standard logs
                            from juju and websockets, as well as debug logs from all other
                            modules. To also include the debug level logs from juju and
                            websockets modules, use the maximum verbosity.
      --quiet, -q           Disable output in STDOUT.
      --machine MACHINES, -m MACHINES
                            Specify machine id(s) to upgrade.
                            This option accepts a single machine id as well as a stringified
                            comma-separated list of ids, and can be repeated multiple times.
                            This option cannot be used together with [--availability-zone/--az].
      --availability-zone AVAILABILITY_ZONES, --az AVAILABILITY_ZONES
                            Specify Juju availability zone(s) to upgrade.
                            This option accepts a single availability zone as well as a
                            stringified comma-separated list of AZs, and can be repeated
                            multiple times. This option cannot be used together with
                            [--machine/-m]
      --auto-approve        Automatically approve and continue with each upgrade step without prompt.
