#!/bin/bash

for device in $(cat device_list); do
    echo "deploy to $device..."
    ssh root@$device 'bash -s' < remote-pre.sh
    scp -r root/* root@$device:/
    ssh root@$device 'bash -s' < remote-post.sh
done