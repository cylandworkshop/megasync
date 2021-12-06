#!/bin/bash

echo "folder: $1"
if [[ -z $1 ]]; then
    echo "no folder"
    exit
fi

for device in $(cat device_list); do
    if [ $(echo $device | cut -c1) != "#" ]; then
        echo "deploy to $device..."
        scp -r $1/* root@$device:/
    fi
done