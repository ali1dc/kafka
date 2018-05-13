#
# Cookbook:: kafka-config
# Recipe:: default
#
# Copyright:: 2018, Ali Jafari - Excella Data Lab, All Rights Reserved.

# script 'apt-get update' do
#   interpreter 'bash'
#   code 'apt-get update'
# end

include_recipe 'confluent-cookbook::default'
include_recipe 'confluent-cookbook::kafka'
include_recipe 'lvm::default'

%w[jq awscli].each do |pkg|
  package pkg
end

# rubocop:disable Naming/HeredocDelimiterNaming

bash 'install python 2.7' do
  code <<-EOH
  sudo apt update
  sudo apt dist-upgrade -y
  sudo apt install python2.7 python-pip -y
  sudo apt install python3-pip -y
  EOH
end

bash 'install-cfn-tools' do
  code <<-SCRIPT
  apt-get update
  apt-get -y install python-setuptools
  mkdir aws-cfn-bootstrap-latest
  curl https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz | tar xz -C aws-cfn-bootstrap-latest --strip-components 1
  easy_install aws-cfn-bootstrap-latest
  SCRIPT
end

python_runtime '2'

%w[kazoo dnspython].each do |package|
  python_package package
end

python_package 'awscli' do
  version '1.14.50'
end

bash 'link correct aws version' do
  code <<-EOH
  rm -rf /usr/bin/aws
  chmod +x /usr/local/bin/aws
  ln -s /usr/local/bin/aws /usr/bin/aws
  EOH
end

package 'ruby'

bash 'install gems' do
  code <<-EOH
  source /usr/local/rvm/scripts/rvm
  gem install aws-sdk keystore
  EOH
end

# Templated scripts
%w[monitor_kafka.py].each do |f|
  template "/usr/local/bin/#{f}" do
    source f
    owner 'root'
    group 'root'
    mode '0755'
  end
end

cookbook_file '/etc/systemd/system/kafka.service' do
  source 'systemd/kafka.service'
  owner 'root'
  group 'root'
  mode '0644'
end

cookbook_file '/etc/default/kafka' do
  source 'systemd/kafka_environment'
  mode '0644'
end

directory '/etc/rsyslog.d'

cookbook_file '/etc/rsyslog.d/66-kafka.conf' do
  source 'systemd/66-kafka.conf'
  mode '0644'
end

directory '/kafkalogs' do
  owner 'confluent'
  group 'confluent'
end

service 'kafka' do
  provider Chef::Provider::Service::Systemd
end

# rubocop:enable Naming/HeredocDelimiterNaming
