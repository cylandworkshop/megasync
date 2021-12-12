#!/bin/bash

SCRIPT=$(readlink -f $0)
SCRIPT_DIR=$(dirname $SCRIPT)

trap ctrl_c INT

function find_usbflash {
    ls /dev/sd*1 2> /dev/null | head -1
}

function ctrl_c() {
    echo "go away by default"

    if ps -p $COPY_SCRIPT > /dev/null; then
        kill $COPY_SCRIPT
    fi

    sudo bash -c "echo 0 >/sys/class/leds/led0/brightness"

    cd /
    if [[ -z $(find_usbflash) ]]; then
        sudo umount $USBFLASH_DIR
    fi
    exit 0
}

list_descendants () {
  local children=$(ps -o pid= --ppid "$1")

  for pid in $children; do
    list_descendants "$pid"
  done

  echo "$children"
}

sudo bash -c "echo none >/sys/class/leds/led0/trigger"

USBFLASH_DIR=/usbflash

function mount_flash {
    if [[ ! -z $(find_usbflash) ]] && \
       [[ -d "$USBFLASH_DIR" ]] && \
       ([[ ! -z $(mount | grep $(find_usbflash)) ]] || sudo mount $(find_usbflash) $USBFLASH_DIR -o ro,uid=$USER,gid=$USER);
    then
        $SCRIPT_DIR/copy-files.sh & COPY_SCRIPT=$!

        # wait for process exists and flash inserted
        while ps -p $COPY_SCRIPT > /dev/null && [[ ! -z $(find_usbflash) ]]; do
            sudo bash -c "echo 1 >/sys/class/leds/led0/brightness"
            sleep 0.1s
            sudo bash -c "echo 0 >/sys/class/leds/led0/brightness"
            sleep 0.1s
        done

        sudo bash -c "echo 0 >/sys/class/leds/led0/brightness"

        echo "end of process or eject flash"

        if ps -p $COPY_SCRIPT > /dev/null; then
            echo "kill $COPY_SCRIPT"
            kill $(list_descendants $COPY_SCRIPT)
            kill $COPY_SCRIPT
        fi
        
        cd /
        if [[ -z $(find_usbflash) ]]; then
            echo "flash ejected"
            
            sudo umount $USBFLASH_DIR
        fi

        sudo bash -c "echo 1 >/sys/class/leds/led0/brightness"

        while [[ $(find_usbflash) ]]; do
            sleep 1s
        done
    else
        if [[ -z "$USBFLASH" ]]; then $()
        elif [[ ! -d "$USBFLASH_DIR" ]]; then echo "$USBFLASH_DIR not exists";
        elif [[ ! -z $(mount | grep $(find_usbflash)) ]]; then echo "not already mounted";
        else echo "mount failed"; fi

        echo "no flash"

        while [[ -z $(find_usbflash) ]]; do
            sudo bash -c "echo 1 >/sys/class/leds/led0/brightness"
            sleep 0.5s
            sudo bash -c "echo 0 >/sys/class/leds/led0/brightness"
            sleep 0.5s
        done
    fi
}

echo "Start script by default"

# try to mount flash infinite
while true; do
    mount_flash
    sleep 0.1s
done
