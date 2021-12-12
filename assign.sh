#!/bin/bash

for x in {38..40}; do
	echo "assign $x"
	ssh root@master-50.local << EOF
		mount -o remount,rw / ;
		echo "slave-$x" > /etc/hostname;
		reboot
EOF
	echo "press enter"
	read
done
