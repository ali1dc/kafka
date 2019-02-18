# frozen_string_literal: true

# rubocop:disable Metrics/MethodLength, Metrics/LineLength, Metrics/AbcSize

require 'erb'
require 'aws-sdk'
require 'trollop'
require 'net/http'

# ENI Switcher
class ENISwitcher
  attr_accessor :eni, :instance

  def lookup_eni(environment, instance_az, instance_id)
    puts environment
    puts instance_id
    eni_id = @ec2.describe_network_interfaces(filters: [
                                                { name: 'tag:Name', values: ['KAFKA-' + '*'] },
                                                { name: 'availability-zone', values: [instance_az] },
                                                { name: 'status', values: ['available'] }
                                              ]).network_interfaces[0]
    if eni_id.nil?
      error = 'No available ENI. Marking instance unhealthy'
      puts error
      @asg.set_instance_health(
        health_status: 'Unhealthy',
        instance_id: instance_id
      )
      raise error
    end
    @resource.network_interface(eni_id.network_interface_id)
  end

  def lookup_instance(instance_id)
    @resource.instance(instance_id)
  end

  def initialize(region)
    @ec2 = Aws::EC2::Client.new(region: region)
    @asg = Aws::AutoScaling::Client.new(region: region)
    @resource = Aws::EC2::Resource.new(client: @ec2)
  end

  def attach_eni(eni, instance_id)
    eni.detach if eni.status == 'in-use' # Only detach ENI's if in use

    puts "Waiting for #{eni.id} to be available"
    # Poll and wait for the ENI to be available
    begin
      @ec2.wait_until(:network_interface_available, network_interface_ids: [eni.id]) do |waiter|
        waiter.interval = 2
        waiter.max_attempts = 60
        waiter.before_attempt { print '.' }
      end
    rescue Aws::Waiters::Errors::WaiterFailed => error
      puts "Timeout waiting for #{eni.id} to detach"
      raise error
    end

    # Attach the ENI
    puts "Attaching #{eni.id} to #{instance_id}"
    eni.attach(instance_id: instance_id, device_index: 1)
  end

  def configure_new_interface(eni_private_ip, instance_ip)
    ipaddr = eni_private_ip
    template = ERB.new File.read('/usr/local/bin/network_config.sh.erb')
    File.write('/usr/local/bin/network_config.sh', template.result(binding))
    File.chmod(0o755, '/usr/local/bin/network_config.sh')
    until system('bash /usr/local/bin/network_config.sh')
      puts 'Error occurred while trying to run /usr/local/bin/network_config.sh'
      sleep 5
    end
  end
end

opts = Trollop.options do
  opt :environment, 'The environemnt', type: String, required: false
  opt :region, 'The AWS Region the instance and ENI live in', type: String, default: 'us-east-1'
end

metadata_endpoint = 'http://169.254.169.254/latest/meta-data/'
instanceid = Net::HTTP.get(URI.parse(metadata_endpoint + 'instance-id'))
puts 'instance_id=' + instanceid
instance_az = Net::HTTP.get(URI.parse(metadata_endpoint + 'placement/availability-zone'))

switcher = ENISwitcher.new(opts[:region])
instance = switcher.lookup_instance(instanceid)
eni = switcher.lookup_eni(opts[:environment], instance_az, instance.id)
switcher.attach_eni(eni, instance.id)
sleep 5
switcher.configure_new_interface(eni.private_ip_address, instance.private_ip_address)
eni_name = eni.tag_set.select { |tag| tag.key == 'Name' }.first.value
File.write('/usr/local/bin/eni_name.sh', "export eni_name=#{eni_name}")

# rubocop:enable Metrics/LineLength, Metrics/MethodLength, Metrics/AbcSize
