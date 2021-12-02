for device in $(cat device_list); do
    if [ $(echo $device | cut -c1) != "#" ]; then
    	echo "restart $device..."
    	ssh root@$device "sudo service bydefault restart"
    fi
done

sleep 5s

server_date=$(ssh pi@192.168.1.2 date +%s)
echo "server date: $server_date"

for device in $(cat device_list); do
	if [ $(echo $device | cut -c1) != "#" ]; then
		echo "send to $device"
		for _ in {0..20}; do
			echo -n "p$(($server_date + 5))" | nc -4u -w0 $device 20001
		done
	fi
done