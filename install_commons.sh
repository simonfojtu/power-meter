#!/bin/bash -e
# usage: $0 <user@host>
#
# Install common packages on the host machine as user

TARGET=$1

PACKAGES="vim git screen build-essential python3-dev virtualenv liblapack-dev"

ssh $TARGET "sudo apt-get install -y $PACKAGES"
