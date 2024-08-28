#!/bin/bash
charts="eric-enm-bro-integration eric-enm-monitoring-integration eric-enm-pre-deploy-integration eric-enm-infra-integration eric-enm-stateless-integration"
declare -A timeouts=( [eric-enm-bro-integration]=300 [eric-enm-monitoring-integration]=900 [eric-enm-pre-deploy-integration]=500 [eric-enm-infra-integration]=18000  [eric-enm-stateless-integration]=14400 )
function prechecks(){
    precheck_failed="no"
    [ ! -f values.yaml ] && precheck_failed="yes" && echo "values.yaml does not exist"
    for c in ${charts[@]}
    do
	num_charts=$(ls $c*.tgz | wc -l)
	if [ ${num_charts} -ne 1 ]; then
	    echo -e "\nThere must only be one instance of $c chart but found ${num_charts}:"
	    ls $c*
	    precheck_failed="yes"
	fi
    done
    if [ "${precheck_failed}" == "yes" ];then
	echo -e "\nPrechecks failed. Exiting..."
	exit 1
    fi
}
function install_chart(){
    local chart=$1
    local c=$(echo $chart | awk '{ gsub(/\-[[:digit:]].*/,"",$1); print $1}')
    status=$(helm ls -n ${ns} -a | awk "/${c}/{ print \$8}")
    if [ "${status}" == "deployed" ]; then
        echo "${chart} is already deployed. Skipping install..."
	return
    fi
    echo "Installing ${chart} as ${c}-${ns} in namespace ${ns}"
    nohup helm install ${c}-${ns}  --values values.yaml ${chart}  --namespace ${ns}  --wait --timeout ${timeouts[$c]} > ${c}.log 2>&1 &
    wait_for_chart $c
}
function wait_for_chart(){
    local chart=$1
    local retries=0
    echo "$(date -Iseconds) Sleep to allow chart to be processed by Helm"
    sleep 15
    status=$(helm ls -n ${ns} -a | awk "/${chart}/{ print \$8}")
    while [ "${status}" != "deployed" ] && [ ${retries} -le 500 ]
    do
	status=$(helm ls -n ${ns} -a | awk "/${chart}/{ print \$8}")
	echo "$(date -Iseconds) ${chart} is in state ${status}. Desired state is 'deployed'"
	[ "${status}" == "failed" ] && echo "$(date -Iseconds) ${chart} is in failed state. Exiting" && exit 1
	retries=$(( retries + 1 ))
        sleep 10
    done
}

# Main
echo -e "Running prechecks\n"
prechecks
echo
echo "Prechecks passed"

ns=$(kubectl get ns |awk '/enm/{ print $1}')
echo "The cENM namespace is ${ns}"
for c in ${charts[@]}
do
    install_chart $c*.tgz
done
