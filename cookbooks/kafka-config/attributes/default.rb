# frozen_string_literal: true

default['java']['jdk_version'] = '8'
default['java']['install_flavor'] = 'oracle'
default['java']['oracle']['accept_oracle_download_terms'] = true

default['confluent']['version'] = '4.1'
default['confluent']['scala_version'] = '2.11'

default['confluent']['kafka']['server.properties'].tap do |broker|
  broker['broker.id'] = 0
  broker['zookeeper.connect'] = 'localhost:2181'
  broker['log.dirs'] = '/kafkalogs/logs'
end