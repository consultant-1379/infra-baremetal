# Define required providers
terraform {
required_version = ">= 0.14.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.35.0"
    }
  }
}

variable "deployment_name" {
  type = string
}

variable "keypair_publickey" {
  type = string
}

variable "network" {
  type = string
  default = "baremetal_client_internal"
}

variable "bmccd_floating_ip" {
  type = string
}

variable "bmccd_fixed_ip" {
  type = string
}

# Configure the OpenStack Provider
# Password, OS_AUTH_URL etc provided by sourcing RC file
provider "openstack" {
  user_name   = "baremetal_client_admin"
  tenant_name = "baremetal_client"
}

data "openstack_images_image_v2" "bmccd_client" {
  name        = "bmccd_client"
}

resource "openstack_compute_keypair_v2" "bmccd-keypair" {
  name = "${var.deployment_name}-keypair"
  public_key = "${var.keypair_publickey}"
}

data "openstack_networking_secgroup_v2" "bmccd_security_group" {
  name = "bmccd_security_group "
}

data "openstack_compute_flavor_v2" "bmccd_client_flavor" {
  name = "bmccd_client_flavor"
}

data "openstack_networking_floatingip_v2" "bmccd_floating_ip" {
  address = "${var.bmccd_floating_ip}"
}
resource "openstack_compute_instance_v2" "bmccd_client_vm" {
  name            = "${var.deployment_name}-client"
  flavor_id       = "${data.openstack_compute_flavor_v2.bmccd_client_flavor.id}"
  key_pair        = "${openstack_compute_keypair_v2.bmccd-keypair.name}"
  security_groups = ["${data.openstack_networking_secgroup_v2.bmccd_security_group.name}"]

  block_device {
    uuid                  = "${data.openstack_images_image_v2.bmccd_client.id}"
    source_type           = "image"
    volume_size           = 200
    boot_index            = 0
    destination_type      = "volume"
    delete_on_termination = true
  }

  network {
    name        = "${var.network}"
    fixed_ip_v4 = "${var.bmccd_fixed_ip}"
  }
}

resource "openstack_compute_floatingip_associate_v2" "floating_ip_associate" {
  floating_ip = "${data.openstack_networking_floatingip_v2.bmccd_floating_ip.address}"
  instance_id = "${openstack_compute_instance_v2.bmccd_client_vm.id}"
  fixed_ip    = "${openstack_compute_instance_v2.bmccd_client_vm.network.0.fixed_ip_v4 }"
}