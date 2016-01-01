#!/usr/bin/env bash

# $1: calendar url
# $2+: source files

cal=$1
shift

title="Rem2GCal"
success="synced to calendar"
failure="failed to sync to calendar"

while true; do
	file=$(inotifywait -q -e modify -e delete_self $* | cut -d ' ' -f 1)
	base=$(basename $file)
	if [ "$base" = 'busy.rem' ]
	then
		gcal.py $file $cal \
			&& notify-send "$title" "$base $success" --icon=dialog-information \
			|| notify-send "$title" "$base $failure" --icon=dialog-warning
	elif [ "$base" = 'free.rem' ]
	then
		gcal.py --free=True $file $cal \
			&& notify-send "$title" "$base $success" --icon=dialog-information \
			|| notify-send "$title" "$base $failure" --icon=dialog-warning
	fi
done

