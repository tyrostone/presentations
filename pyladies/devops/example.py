#!/usr/bin/python
#
# Sanitized script from PyLadies 'Intro to DevOps' presentation
# An example of using Python to interact with AWS
# Also, some server stuff
#
import boto
import os
import shutil
import subprocess
import sys
import time

import boto.ec2
import boto.ec2.autoscale
from boto.ec2.autoscale.launchconfig import LaunchConfiguration


KEY_NAME = ""
REGION = ""


def setup_credentials():
    try:
        AWS_ACCESS_KEY = os.environ["AWS_ACCESS_KEY_ID"]
        AWS_SECRET_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
    except KeyError:
        try:
            # Open ~/.aws/credentials file and read default
            home = os.environ['HOME']
            f = open(home + '/.aws/credentials', 'r')
            content = f.read()
            index = content.splitlines().index("[default]")
        except IOError, ValueError:
            print("----------------------------------------------------------")
            print("Please consider exporting your AWS access and secret keys.")
            print("----------------------------------------------------------")
            AWS_ACCESS_KEY = raw_input("Please enter your AWS access key: ")
            AWS_SECRET_KEY = raw_input("Please enter your AWS secret key: ")
            os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY
            os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_KEY
    return True


def setup_connection():
    global ec2_connection
    global autoscaling_connection
    ec2_connection = boto.ec2.connect_to_region(REGION)
    autoscaling_connection = boto.ec2.autoscale.connect_to_region(REGION)
    return ec2_connection, autoscaling_connection


def run_instance(ami_id):
    r = ec2_connection.run_instances(ami_id, key_name=KEY_NAME, security_group_ids=[],
                                     instance_type="", subnet_id="")
    instance = r.instances[0]
    wait_for_state("running", instance)

    tagged = tag_instance(instance)
    eip = get_eip()
    if eip is None:
        print "EIP came back as None. Check that you have EIPs allocated."
        sys.exit(1)
    print "Attaching EIP %s to instance %s" % (eip.public_ip, instance.id)
    eip_attached = attach_eip_to_instance(instance.id, eip.allocation_id)

    if tagged and eip_attached:
        return instance, eip.public_ip
    return None


def get_eip():
    free_eips = [x for x in ec2_connection.get_all_addresses() if x.association_id is None]
    for eip in free_eips:
        if eip.domain == "vpc":
            return eip
    return None


def attach_eip_to_instance(instance, eipalloc):
    attached = False
    try:
        ec2_connection.associate_address(instance_id=instance, public_ip=None, allocation_id=eipalloc)
        attached = True
    except Exception, e:
        print e
    return attached


def tag_instance(instance):
    wait_for_state("running", instance)
    instance.add_tag("Name", "PUPPET-FODDER")
    return True


def wait_for_state(state, instance):
    status = instance.update()
    while status != state:
        time.sleep(5)
        status = instance.update()
        print "Instance %s status: %s " % (instance.id, status)


def wait_for_ssh(instance):
    while ssh(str(instance), 'true'):
        time.sleep(1)
    print "SSH up for %s" % (instance)


def ssh(hostname, *args, **kwargs):
    username = kwargs.pop('username', 'centos')

    cmd = ('ssh', '-t',
           '-o', 'UserKnownHostsFile=/dev/null',
           '-o', 'StrictHostKeyChecking=no',
           '{username}@{hostname}'.format(**locals())
           ) + args
    return subprocess.call(cmd, **kwargs)


def scp(hostname, *args, **kwargs):
    username = kwargs.pop('username', 'centos')

    filename = os.path.abspath(".") + "/work/puppet-bastion"
    remotepath = "/home/centos"

    cmd = ('scp',
           '-o', 'UserKnownHostsFile=/dev/null',
           '-o', 'StrictHostKeyChecking=no',
           '-o', 'BatchMode=yes',
           '-r', '{filename}'.format(**locals()),
           '{username}@{hostname}:{remotepath}'.format(**locals())
           ) + args
    return subprocess.Popen(cmd, **kwargs)


def install_and_apply_puppet(path, hostname):
    install_puppet(hostname)
    copy_puppet_to_modulepath(hostname)
    apply_puppet(hostname)


def install_puppet(hostname, command="/home/centos/puppet-bastion/puppet-install.sh"):
    while ssh(hostname, command):
        time.sleep(30)


def copy_puppet_to_modulepath(hostname, command='sudo su - -c "cp -r /home/centos/puppet-bastion/* /etc/puppet"'):
    while ssh(hostname, command):
        time.sleep(10)


def apply_puppet(hostname, command='sudo su - -c "puppet apply /etc/puppet/manifests/site.pp"'):
    while ssh(hostname, command):
        print "Applying puppet to instance %s" % (hostname)
        time.sleep(400)
    print "Puppet applied to instance %s" % (hostname)


def flush_iptables(hostname, command='sudo su - -c "iptables --flush"'):
    while ssh(hostname, command):
        time.sleep(10)


def clone_repo(path, link):
    work = create_work_directory(path)
    if work:
        try:
            p = subprocess.Popen(["git", "clone", link], cwd=work)
            p.communicate()
            return True
        except Exception, e:
            print("Unable to clone repo: {}".format(str(e)))
    sys.exit(1)


def create_work_directory(path):
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except Exception, e:
        print("Unable to create directory: {}".format(str(e)))
        return None
    return path


def ensure_puppet_parity(path):
    sources_home = path + "/archmp-scanner-provisioning"
    if not os.path.exists(sources_home):
        raise OSError("Path to puppet repo not found")

    sources = [sources_home + "/manifests",
               sources_home + "/modules",
               sources_home + "/puppet-install.sh"]

    target = path + "/puppet-bastion/"
    if not os.path.exists(target):
        os.makedirs(target)

    for source in sources:
        print source
        cmd = ('cp', '-r', '{source}'.format(**locals()), '{target}'.format(**locals()))
        subprocess.call(cmd)


def create_ami(instance):
    ami_id = instance.create_image(name=get_name("ami"),
                                   description=" %s" % (get_name("ami")[-3:]))
    ami = ec2_connection.get_all_images(image_ids=ami_id)[0]
    return ami


def create_launch_configuration(ami):
    lc_name = get_name("lc")
    user_data = "#!/bin/bash" + "\n" + "/usr/local/pyenv/shims/python /tmp/script.py"
    lc = LaunchConfiguration(name=lc_name,
                             image_id=str(ami.id),
                             key_name=KEY_NAME,
                             security_groups=[],
                             instance_type="",
                             user_data=user_data,
                             instance_profile_name="",
                             associate_public_ip_address=False,
                             )

    autoscaling_connection.create_launch_configuration(lc)


def get_name(n):
    nlist = []
    name = ""
    try:
        if n == "lc":
            nlist = autoscaling_connection.get_all_launch_configurations()
            name = ""
        elif n == "ami":
            nlist = ec2_connection.get_all_images(owners='self')
            name = ""
        versions = [int(x.name[len(name):]) for x in nlist]
        versions.sort()
        latest_version = versions[-1]
        new_version = latest_version + 1
    except IndexError, e:
        new_version = 1
    return name + str(new_version)


def cleanup(path):
    if os.path.exists(path):
        shutil.rmtree(path)


if __name__ == "__main__":
    # Verablessed CentOS AMI
    ami = ""
    project_path = os.path.abspath(".") + "/work"
    puppet_repo = ""

    # Setup AWS credentials and connection to EC2
    creds = setup_credentials()
    setup_connection()

    clone_repo(project_path, puppet_repo)
    ensure_puppet_parity(project_path)

    if creds:
        instance, ip = run_instance(ami)
        wait_for_ssh(ip)
        while scp(ip).wait():
            time.sleep(60)
        install_and_apply_puppet(project_path, ip)

        ami = create_ami(instance)
        wait_for_state("available", ami)

        create_launch_configuration(ami)

        # Terminate instance after Launch Configuration is created
        ec2_connection.terminate_instances(instance.id)

    # Remove work subdirectories
    cleanup(project_path)
