sudo rpm -ivh http://yum.puppetlabs.com/puppetlabs-release-el-6.noarch.rpm
sudo yum install -y puppet
if [ ! -d /etc/puppet/modules ]; then
    sudo mkdir /etc/puppet/modules
fi
sudo puppet module install puppetlabs-concat --modulepath /etc/puppet/modules
sudo puppet module install puppetlabs-vcsrepo --modulepath /etc/puppet/modules
sudo puppet module install jfryman-nginx --modulepath /etc/puppet/modules
