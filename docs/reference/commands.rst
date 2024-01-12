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

    Options:
    -h, --help        	Show this help message and exit.
    --model MODEL_NAME	Set the model to operate on.
                            If not set, the currently active Juju model will be used.
    --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
    --verbose, -v     	Increase logging verbosity in STDOUT. Multiple 'v's yield progressively more detail (up to 4).
                            Note that by default the logfile will include standard logs from juju and websockets, as well as debug logs from all other modules. To also include the debug level logs from juju and websockets modules, use the maximum verbosity.
    --quiet, -q       	Disable output in STDOUT.

Upgrade
-------

The **upgrade** command will implicitly generate a plan before moving onto the actual
upgrade phase. Refer to the output below for a description of all available options. 

.. terminal:: 
    :input: cou upgrade --help
    
    Usage: cou upgrade [options]

    Run the cloud upgrade.

    Options:
    -h, --help        	Show this help message and exit.
    --model MODEL_NAME	Set the model to operate on.
                            If not set, the currently active Juju model will be used.
    --backup, --no-backup
                            Include database backup step before cloud upgrade.
                            Default to enabling database backup.
    --verbose, -v     	Increase logging verbosity in STDOUT. Multiple 'v's yield progressively more detail (up to 4).
                            Note that by default the logfile will include standard logs from juju and websockets, as well as debug logs from all other modules. To also include the debug level logs from juju and websockets modules, use the maximum verbosity.
    --quiet, -q       	Disable output in STDOUT.
    --auto-approve    	Automatically approve and continue with each upgrade step without prompt.

