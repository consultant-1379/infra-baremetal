#!/bin/bash
deployment_name=$1
shift 1
[ -z ${deployment_name} ] && echo "Please provide a deployment name e.g. bmccd1" && exit 1
echo "Baremetal CCD deployment ${deployment_name}" 
script_dir="$(dirname $(readlink -f $0))"
ccd_dir="${script_dir}/deployments"
deploy_dir="${ccd_dir}/${deployment_name}"
if [ ! -d ${deploy_dir} ];then
    echo "${deploy_dir} does not exist."
    exit 1
fi
ansible-playbook -i $deploy_dir/ccd_inventory.yml $script_dir/site.yml -e ccddir=${ccd_dir} -e @$deploy_dir/${deployment_name}.yml $@
