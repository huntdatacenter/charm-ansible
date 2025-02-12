#!/usr/bin/bash

# start new detached tmux session
tmux new-session -d -s workspace  # "bash --login bin/bootstrap.sh"

sleep 1

tmux send-keys -t workspace "bash --login bin/bootstrap.sh" Enter

sleep 1

# split the detached tmux session - vertically
tmux split-window -v

# split the detached tmux session - horizontally
tmux split-window -h

# send 2nd command 'htop -t' to 2nd pane. I believe there's a `--target` option to target specific pane.
# tmux send 'htop -t' ENTER

# open (attach) tmux session.
tmux a -t workspace
