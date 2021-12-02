#!/bin/bash

echo "script: $1"

for device in $(cat device_list); do
    if [ $(echo $device | cut -c1) != "#" ]; then
        echo "run on $device..."
        ssh root@$device 'bash -s' < $1
    fi
done