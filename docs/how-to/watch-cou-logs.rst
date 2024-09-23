==============
Watch COU logs
==============

Below is the script to watch the COU logs when doing the development.
This script watches every log file in the directory, even newly created files.

.. code:: bash

    #!/bin/bash

    # Change LOG_DIR to the target directory
    DIRECTORY="$HOME/.local/share/cou/log/"
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
