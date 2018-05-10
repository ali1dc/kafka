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
