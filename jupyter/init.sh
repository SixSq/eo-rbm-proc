#!/bin/bash

token=`cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 15 | head -n 1`
echo "generated access token: ${token}"
echo -n ${token} > /home/jovyan/token.txt

# taken from https://raw.githubusercontent.com/nuvla/example-jupyter/master/nuvla-integration.py
python /usr/local/bin/nuvla-integration.py
rm -f /home/jovyan/token.txt

export GEN_CERT=yes

jupyter notebook --NotebookApp.token=${token} --allow-root --ip=0.0.0.0 "$@"
