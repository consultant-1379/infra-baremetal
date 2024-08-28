#!/bin/bash
san_type=$(echo $1 | tr '[[:upper:]]' '[[:lower:]]')
if [ -n "${san_type}" ]; then
    if [ "${san_type}" == "unity" ];then
        ansible-playbook --skip-tags 3par --ask-vault-pass test_config_san.yml
    elif [ "${san_type}" == "3par" ]; then
        ansible-playbook -i deployments/bmccd2/infra_inventory.yml test_config_san.yml --skip-tags unity --ask-vault-pass
    else
        echo "${san_type} is not a supported storage array"
        exit 1
    fi
else
    echo -e "\nScript to test configure_san role for 3par or Unity\n\nUsage:\n\n./test_config_san.sh <san_type>\n\nsan_type\t3par or unity"
    exit 1
fi