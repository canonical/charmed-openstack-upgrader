===============================
Test on Juju OpenStack provider
===============================

This document explain how to setup the testing environment on top of the Juju OpenStack provider and how to run COU testing.


Bootstrap juju controller on openstack cloud
--------------------------------------------

Follow the step on the `official document <https://juju.is/docs/juju/manage-controllers#heading--bootstrap-a-controller>`_ to bootstrap a Juju Openstack controller


Deploy openstack with juju openstack-provider
---------------------------------------------

Follow the step on `STSStack Bundles <https://github.com/canonical/stsstack-bundles>`_
to deploy the openstack cloud


.. code::

    git clone https://github.com/canonical/stsstack-bundles.git
    cd openstack

    # Some of the overlays may be missing here, check all the supported overlays with:
    ./generate-bundle.sh --list-overlays

    # ussuri-focal is the lowest version that COU supports
    ./generate-bundle.sh --name some-juju-model-name -r ussuri -s focal --ovn --telemetry


(Optional) sshuttle as proxy
-------------------

If your openstack environment is behind the vpn and you have the bastion server, you can use sshuttle:

.. code:: bash

     sshuttle --ssh-cmd "ssh -i /home/myuser/.ssh/mykey" -v -r ubuntu@your-bastion-ip 10.5.0.0/16


Prepare local python environment for COU
----------------------------------------

.. code:: bash

    virtualenv ./.venv
    source .venv/bin/activate
    pip install -e .

    # (Optional)
    # Copy all the files under ~/.local/share/juju to ./juju-data
    export JUJU_DATA=./juju-data


Execute the COU
---------------

Run cou plan and review the steps generate by COU

.. code:: bash

    python -m cou plan


(Optional) Run apply to execute the upgrade steps

.. code:: bash

    python -m cou apply


(Optional) Tail COU's log message
-------------------------------------

Use below script to tail the log files with follow mode:

.. code:: bash

   #!/bin/bash

   DIRECTORY="/home/myuser/.local/share/cou/log/"
   CHECK_INTERVAL=2  # Check for new files every 2 seconds
   LOGFILE=".tailed_files.log"

   # Function to tail new files
   tail_files() {
       for file in "$DIRECTORY"/*; do
           if [ -f "$file" ] && ! grep -q "$file" "$LOGFILE"; then
               echo "Tailing new file: $file"
               tail -F "$file" &
               echo "$file" >> "$LOGFILE"
           fi
       done
   }

   # Function to clean up logfile on exit
   cleanup() {
       echo "Cleaning up..."
       rm -f "$LOGFILE"
       exit 0
   }

   # Set trap to clean up logfile on exit
   trap cleanup EXIT

   # Create or clear the log file
   > "$LOGFILE"

   # Initial tailing of existing files
   tail_files

   # Periodically check for new files and tail them
   while true; do
       sleep "$CHECK_INTERVAL"
       tail_files
   done
