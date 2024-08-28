# README

## Source

The HPE 3PAR Ansible module has been downloaded from github: https://github.com/HewlettPackard/hpe3par_ansible_module/archive/d35d73386265fe0d2308ff1eeacb86ed564de7d1.zip
The contents of Modules directory (from the zip file) has been added to roles/configure_san/library/ to make it HPE 3PAR modules available to the role.
The latest commit at the time of download was: https://github.com/HewlettPackard/hpe3par_ansible_module/commit/d35d73386265fe0d2308ff1eeacb86ed564de7d1

## Modifications

The HPE 3PAR ansible module does not allow the creation of a Virtual Volume (VV) with a particular ID.
I have updated the code to allow the volume_id to be passed as a parameter to the hpe_3par_volume module.
The diff between the updated code and the original is below:

hpe3par_ansible_module-master/Modules/hpe3par_volume.py
Added a _vv_id_ parameter to the _create_volume_ method:

@@ -324,11 +324,11 @@

```python
         cpg,
         size,
         size_unit,
         type,
         compression,
-        snap_cpg):
+        snap_cpg,vv_id):
     if storage_system_username is None or storage_system_password is None:
         return (
             False,
             False,
             "Volume creation failed. Storage system username or password is \
@@ -365,11 +365,11 @@
                 tpvv = True
             elif type == 'thin_dedupe':
                 tdvv = True
             size_in_mib = convert_to_binary_multiple(
                 size, size_unit)
-            optional = {'tpvv': tpvv, 'tdvv': tdvv, 'snapCPG': snap_cpg,
+            optional = {'id':vv_id,'tpvv': tpvv, 'tdvv': tdvv, 'snapCPG': snap_cpg,
                         'compression': compression,
                         'objectKeyValues': [
                             {'key': 'type', 'value': 'ansible-3par-client'}]}
             client_obj.createVolume(volume_name, cpg, size_in_mib, optional)
         else:
```
Added a _volume_id_ parameter to the module spec
@@ -792,10 +792,13 @@
```python
         },
         "volume_name": {
             "required": True,
             "type": "str"
         },
+        "volume_id":{
+            "type": "int"
+        },
         "cpg": {
             "type": "str",
             "default": None
         },
         "size": {
```

Updated to pass the _volume_id_ parameter to the _create_volume_ call.
@@ -906,21 +909,21 @@

```python
     rm_usr_spc_alloc_limit = module.params["rm_usr_spc_alloc_limit"]
     rm_ss_spc_alloc_limit = module.params["rm_ss_spc_alloc_limit"]
     compression = module.params["compression"]
     keep_vv = module.params["keep_vv"]
     type = module.params["type"]
-
+    volume_id = module.params["volume_id"]
     port_number = client.HPE3ParClient.getPortNumber(
         storage_system_ip, storage_system_username, storage_system_password)
     wsapi_url = 'https://%s:%s/api/v1' % (storage_system_ip, port_number)
     client_obj = client.HPE3ParClient(wsapi_url, 'ansible_module_3par')

     # States
     if module.params["state"] == "present":
         return_status, changed, msg, issue_attr_dict = create_volume(
             client_obj, storage_system_username, storage_system_password,
-            volume_name, cpg, size, size_unit, type, compression, snap_cpg)
+            volume_name, cpg, size, size_unit, type, compression, snap_cpg,vv_id=volume_id)
     elif module.params["state"] == "absent":
         return_status, changed, msg, issue_attr_dict = delete_volume(
             client_obj, storage_system_username, storage_system_password,
             volume_name)
     elif module.params["state"] == "grow":

```
Additionally, there is a bug in the _export_volume_to_host_ method in hpe3par_vlun.py. If the lunid is zero, the if lunid evaluates to false. Updated the condition to check if the value is not None.
```python
(3par) ejamduf@IAAS-NETINF24:/tmp/jd$ diff -u5 hpe3par_ansible_module-master/Modules/hpe3par_vlun.py  ~/gitrepos/infra-baremetal/roles/configure_san/library/hpe3par_vlun.py
--- hpe3par_ansible_module-master/Modules/hpe3par_vlun.py       2020-08-25 13:40:59.000000000 +0100
+++ /home/ejamduf/gitrepos/infra-baremetal/roles/configure_san/library/hpe3par_vlun.py  2021-01-12 15:31:24.950000000 +0000
@@ -223,11 +223,11 @@
                 port_pos,
                 None,
                 None,
                 autolun)
         else:
-            if lunid:
+            if lunid is not None and type(lunid) == int:
                 if not client_obj.vlunExists(
                         volume_name, lunid, host_name, port_pos):
                     client_obj.createVLUN(
                         volume_name,
                         lunid,
```