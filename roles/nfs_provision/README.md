NFS Provision
=========

Creates file systems on a NAS, exports them via NFS and creates [PersistentVolume](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) objects in a Kubernetes Cluster

Requirements
------------

### Required Modules
- PyPowerStore module when using DellEMC PowerStore appliance

Role Variables
--------------

| Variable Name | Description |
|----------|-------|
| pvc_ns | K8s Namespace for the PersistentVolumeClaims which will consume the PersistentVolumes created by this role. |
| cenm_xl| Set to True for XL cENM deployments otherwise set to False. Defaults to False.|
|    rcd_index_data      |  The URL to retrieve the list of product set versions. This is set to "https://resourceconfigurationdata.internal.ericsson.com/data/index.json"  in nfs_provision/vars.yml.   |
|   rcd_xl_url       |  The URL to retrieve the Resource Configuration Data for cENM XL. This is set in   nfs_provision/vars.yml.   |
|    rcd_url      |    The URL to retrieve the Resource Configuration Data for Small cENM. This is set in   nfs_provision/vars.yml.   |



Dependencies
------------

N/A

Example Playbook
----------------

N/A

License
-------

????

Author Information
------------------

Created by James Duffy (ejamduf)
