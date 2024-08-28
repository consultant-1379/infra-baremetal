#!/bin/bash
. common.bsh

trap "abort 'Ctrl-C pressed'" SIGINT

check_dependencies(){
    which python3
    python3_installed=$?
    [ ${python3_installed} -eq 0 ] || error "python3 is required but not installed"
    which pip3
    pip3_installed=$?
    [ ${pip3_installed} -eq 0 ] || error "pip3 is required but not installed"

    [[ ${pip3_installed} -eq 0 && ${python3_installed} -eq 0 ]] || abort "Python3/Pip3 are not installed"

    info "Check if AWX CLI (awxkit python package) is installed"

    if ! pip3 list |& grep awxkit; then
        info "Installing AWX CLI"
        pip3 install --user https://releases.ansible.com/ansible-tower/cli/ansible-tower-cli-latest.tar.gz
    fi
}
# set_virtualenv(){
#     unset custom_venv
#     echo "Do you want to use a custom python virtual environment? (y/n)"
#     read -r answer
#     if [ "${answer}" == "y" ];then
#         info "Get list of virtual environments from AWX"
#         venvs=$(curl -s -u "osinfra:${password}"  "${TOWER_HOST}/api/v2/config/" | jq .custom_virtualenvs[] | tr -d '"')

#         export PS3="Select a Python Virtual Environment:"
#         # shellcheck disable=SC2068
#         select venv in ${venvs[@]}
#         do
#         if [ -n "${venv}" ]; then
#             info "selected ${venv}"
#             export custom_venv="${venv}"
#             break
#         else
#             continue
#         fi
#         done
#     else
#         info "Using default virtual environments: /var/lib/awx/venv/ansible/"
#         export custom_venv="/var/lib/awx/venv/ansible/"
#     fi
# }
get_patchset_info(){
    info "Getting Change-Id"
    change_id=$(git show -s | awk '/Change-Id/{ print $2 }')
    info "Change-Id is ${change_id}"

    info "Getting project name"
    project=$(git remote -v | awk '{ print $2 }' | uniq|sed -r 's#.*(OSS.*)#\1#g')
    info "Project is ${project}"

    info "Getting gerrit ref"
    # shellcheck disable=SC2029
    project_info=$(ssh -p 29418 gerrit.ericsson.se "gerrit query --format=JSON  change:${change_id} --current-patch-set status:open project:${project}")

    rows=$( echo "${project_info}"| jq .rowCount | grep -v null)
    if [ $rows -eq 0 ]; then
        is_master="yes"
    else
        # 'grep -v null' required as gerrit returns to separate JSON objects(i.e. not a list of 2 objects)
        project_ref=$( echo "${project_info}" | jq .currentPatchSet.ref | grep -v null | tr -d '"')
        commit_id=$( echo "${project_info}" | jq .currentPatchSet.revision | grep -v null | tr -d '"')
        patch_owner=$( echo "${project_info}" | jq .owner.username | grep -v null | tr -d '"' )
        info "project ref is ${project_ref}"
    fi
}

awx_create_job(){
    echo "Enter the 'osinfra' user's password:"
    read -esr password
    echo
    info "Logging into AWX Tower"
    # shellcheck disable=SC2155
    export TOWER_OAUTH_TOKEN=$(awx login --conf.host "${TOWER_HOST}" --conf.username osinfra --conf.password "${password}" --conf.insecure | jq .token | tr -d '"')
        
    info "Creating project"
    if [ "${is_master}" == "yes" ]; then
        awx_project="${USER}_test_$(echo $project | sed -r 's/.*\/(.*$)/\1/g' )_${change_id}"
        awx projects create -k --wait \
            --organization DE --name="${awx_project}" \
            --scm_type git --scm_url "ssh://deosinfra@gerrit.ericsson.se:29418/${project}" \
            --scm_branch "master" \
            --scm_delete_on_update true \
            --credential  "$(awx credentials list --all -f json | jq '.results[] | select(.name=="deosinfra").id')" -f human
    else
        # shellcheck disable=SC2086
        awx_project="${patch_owner}_test_$(echo $project | sed -r 's/.*\/(.*$)/\1/g' )_${change_id}"
        awx projects create -k --wait \
            --organization DE --name="${awx_project}" \
            --scm_type git --scm_url "ssh://deosinfra@gerrit.ericsson.se:29418/${project}" \
            --scm_branch "${commit_id}" \
            --scm_refspec "${project_ref}"  \
            --scm_delete_on_update true \
            --credential  "$(awx credentials list --all -f json | jq '.results[] | select(.name=="deosinfra").id')" -f human
    fi
    if [ -n "${check_inventory_in_awx}" ];then
        info "Check if ${inventory} exists in AWX"
        if ! awx inventory get  "${inventory}"; then
            abort "${inventory} does not exist in AWX"
        else
            info "${inventory} exists in AWX"
        fi
    else
        info "Creating inventory ${deployment}"
        awx inventory create -f human --name "${deployment}"  --organization DE
        info "Adding source for inventory ${deployment}"
        awx inventory_source create -f human  --source_path "${inventory}" --source scm --source_project "${awx_project}" --update_on_launch true --inventory "${deployment}" --name "${deployment}_src"
        export inventory=${deployment}
    fi
    # set_virtualenv
    export custom_venv="/opt/customvenv/baremetal/"
    info "Selected virtual environment is ${custom_venv}"
    job_name="Test: ${deployment} ${playbook} ${patch_owner}"
    info "Creating job template"
    # shellcheck disable=SC2155
    export awx_job_id=$(
        awx job_templates create -k \
        --name="${job_name}" --project "${awx_project}" --forks 30 --ask_credential_on_launch true \
        --custom_virtualenv "${custom_venv}" --extra_vars @extra_vars.yml \
        --skip_tags "${tags_to_skip}" \
        --playbook "${playbook}" --inventory "${inventory}"  -f json --conf.color False | jq .id)

    info "Launching job: ${job_name}"
    #awx job_templates launch --credentials "deployment_password,Baremetal,awx_ssh_as_root" -k "${awx_job_id}" --monitor -f human
    
    awx job_templates launch --credentials "deployment_password,DE_INFRA_C16AF01,awx_ssh_as_root" -k "${awx_job_id}" --monitor -f human
}
delete_awx_items(){
    echo "Delete job, inventory & project (y/n)"
    read -r answer
    if [ "${answer}" == "y" ]; then
    info "Deleting job template"
    awx job_templates delete "${awx_job_id}"

    # info "Deleting inventory ${deployment}"
    # awx inventory delete "${deployment}"

    info "Deleting project ${awx_project}"
    awx projects delete "${awx_project}"
    fi
}
check_prequisites_met(){

    info "Checking this script is running from the correct directory"

    if [ "$(pwd)" != "${script_dir}" ]; then
        abort "This script must be run from ${script_dir}"
    fi
    info "Script running from correct directory"

    if [[ "${inventory}" =~ .y[a]?ml$ ]]; then
        info "Checking inventory ${inventory} exists."
        if [ ! -e "${inventory}" ];then
            abort "${inventory} does not exist"
        fi
    export deployment=$(echo ${inventory} | cut -d '/' -f2)
    else
        export check_inventory_in_awx=yes
        export deployment=$(echo ${inventory} | cut -d '_' -f1)
    fi
    info "Checking deployment ${deployment} exists"
    deployment_file="deployments/${deployment}/${deployment}.yml"
    # if [ ! -e "${deployment_file}" ]; then
    #     abort "${deployment_file} does not exist"
    # fi
}
usage(){
    msg="Usage:\n./runit.sh <playbook> <inventory> <tags to skip>\n\nExample\n\n./runit.sh build_bm.yml deployments/bmccd1/infra_inventory.yml\n"
    echo -e "${msg}"
}
# Main
if [ $# -ge 2 ]; then
    # shellcheck disable=SC2155,SC2046,SC2086
    export script_dir="$(dirname $(readlink -f $0))"
    export playbook=$1
    export inventory=$2
    export tags_to_skip=$3
    export TOWER_HOST=http://ieatansible4b.athtem.eei.ericsson.se
    check_prequisites_met
    check_dependencies
    get_patchset_info
    awx_create_job
    delete_awx_items
else
    usage
fi
