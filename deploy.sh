#!/bin/bash

echo "folder: $1"
if [[ -z $1 ]]; then
    echo "no folder"
    exit
fi

if [[ $2 ]]; then
    echo "single deploy to $2.."
    scp -r $1/* root@$2:/
else
    for device in $(cat device_list); do
        if [ $(echo $device | cut -c1) != "#" ]; then
            echo "deploy to $device..."
            scp -r $1/* root@$device:/
        fi
    done
fi