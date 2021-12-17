./run.sh set_rw.sh $1
./deploy.sh scripts/ $1
./deploy.sh grids/ $1
./run.sh set_ro.sh $1
./run.sh bydefault-start.sh $1
