#!/bin/bash

SCRIPT=$(readlink -f $0)
SCRIPT_DIR=$(dirname $SCRIPT)

trap ctrl_c INT

function ctrl_c() {
    echo "go away by default"
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

while true; do
    sudo bash -c "echo 1 >/sys/class/leds/led0/brightness"
    sleep 0.2s
    sudo bash -c "echo 0 >/sys/class/leds/led0/brightness"
    sleep 0.2s
done

