#!/bin/bash
script_dir="$(dirname $(readlink -f $0))"
ansible-playbook init_bm_info.yml -e topdir=${script_dir}