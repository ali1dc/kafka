# frozen_string_literal: true

#
# Cookbook:: kafka-config
# Recipe:: default
#
# Copyright:: 2018, Ali Jafari - Excella Data Lab, All Rights Reserved.

include_recipe 'confluent-cookbook::default'
include_recipe 'confluent-cookbook::kafka'
include_recipe 'lvm::default'

%w[jq awscli ruby].each do |pkg|
  package pkg
end

# rubocop:disable Naming/HeredocDelimiterNaming

bash 'install-cfn-tools' do
  code <<-SCRIPT
  apt-get update
  apt-get -y install python-setuptools
  mkdir aws-cfn-bootstrap-latest
  curl https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz | tar xz -C aws-cfn-bootstrap-latest --strip-components 1
  easy_install aws-cfn-bootstrap-latest
  SCRIPT
end

# python_runtime '2'
python_runtime '2' do
  # Workaround for https://github.com/poise/poise-python/issues/133
  get_pip_url 'https://github.com/pypa/get-pip/raw/f88ab195ecdf2f0001ed21443e247fb32265cabb/get-pip.py'
  pip_version '18.0'
end

%w[kazoo dnspython boto].each do |package|
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

# package 'ruby'
bash 'install rvm' do
  code <<-EOH
  sudo apt-get purge ruby
  sudo apt-get install software-properties-common
  sudo apt-add-repository -y ppa:rael-gc/rvm
  sudo apt-get update
  sudo apt-get install rvm -y
  sudo /usr/share/rvm/bin/rvm install ruby 2.5.3
  EOH
end

# source /usr/local/rvm/scripts/rvm
bash 'install gems' do
  code <<-EOH
  source /usr/share/rvm/scripts/rvm
  rvm use 2.5.3
  gem install aws-sdk keystore
  EOH
end

# for user root
bash 'install rvm and ruby as root' do
  user 'root'
  code <<-EOH
  apt-get install software-properties-common
  apt-add-repository -y ppa:rael-gc/rvm
  apt-get update
  apt-get install rvm -y
  /usr/share/rvm/bin/rvm install ruby 2.5.3
  source /usr/share/rvm/scripts/rvm
  rvm reinstall 2.5.3
  gem install aws-sdk keystore
  EOH
end

# Templated scripts
%w[monitor_kafka.py attach_ebs.py].each do |f|
  template "/usr/local/bin/#{f}" do
    source f
    owner 'root'
    group 'root'
    mode '0755'
  end
end

%w[network_config.sh.erb eni_switcher.rb].each do |f|
  cookbook_file "/usr/local/bin/#{f}" do
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

# Prometheus jmx exporter
directory '/opt/prometheus'

prometheus_agent = 'https://repo1.maven.org/maven2/io/prometheus/jmx/' \
                   'jmx_prometheus_javaagent/0.6/' \
                   'jmx_prometheus_javaagent-0.6.jar'
remote_file '/opt/prometheus/jmx_prometheus_javaagent-0.6.jar' do
  source prometheus_agent
end

cookbook_file '/opt/prometheus/kafka.yml' do
  source 'prometheus-kafka.yml'
end

# rubocop:enable Naming/HeredocDelimiterNaming
