#!/bin/bash

dir=/media/aanper/USB\ STICK/worktown

for i in {1..40}; do
	echo "upload to $i.local"
	./run.sh set_rw.sh slave-$i.local
	scp "$dir"/$i.mp4 root@slave-$i.local:/data
	./run.sh set_ro.sh $i.local
done
