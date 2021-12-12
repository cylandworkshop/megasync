#!/bin/bash
 
echo "Default usb script, copy file"
sudo mount -o remount,rw /data
cp /usbflash/synctest.mp4 /data/
sudo mount -o remount,ro /data