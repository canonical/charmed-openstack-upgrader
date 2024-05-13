#!/bin/bash
# This is a template `rename.sh` file for snaps
# This file is managed by bootstack-charms-spec and should not be modified
# within individual snap repos. https://launchpad.net/bootstack-charms-spec

file_name=$(ls *.snap)
snap=$(grep -E "^name:" snap/snapcraft.yaml | awk '{print $2}')
arch=$(echo "$file_name" | awk -F'_' '{print $NF}' | awk -F'.' '{print $(NF-1)}')
echo "renaming ${file_name} to ${snap}_${arch}.snap"
echo -n "pwd: "
pwd
ls -al
echo "Removing previous snap if it exists"
if [[ -e "${snap}_${arch}.snap" ]];
then
    rm "${snap}_${arch}.snap"
fi
echo "Renaming snap here."
mv ${file_name} ${snap}_${arch}.snap
