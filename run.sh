#!/bin/bash

echo "script: $1"

if [[ $2 ]]; then
    echo "single run on $2.."
    ssh root@$2 'bash -s' < $1
else
    for device in $(cat device_list); do
        if [ $(echo $device | cut -c1) != "#" ]; then
            echo "run on $device..."
            ssh root@$device 'bash -s' < $1
        fi
    done
fi