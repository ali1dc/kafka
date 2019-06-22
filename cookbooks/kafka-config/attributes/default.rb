# frozen_string_literal: true

default['java']['jdk_version'] = '8'
default['confluent']['version'] = '4.1'
default['confluent']['scala_version'] = '2.11'

default['confluent']['kafka']['server.properties'].tap do |broker|
  broker['broker.id'] = 0
  broker['listeners'] = 'PLAINTEXT://IP:9092'
  broker['advertised.listeners'] = 'PLAINTEXT://IP:9092'
  broker['zookeeper.connect'] = \
    '10.100.1.100:2181,10.100.2.100:2181,10.100.3.100:2181'
  broker['log.dirs'] = '/kafkalogs/logs'
end

override['poise-python']['options']['pip_version'] = '9.0.3'
