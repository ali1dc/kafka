In this article, I want to talk about a challenging task; deploying Apache Kafka as service on AWS. But before I deep dive, let's see what is Apache Kafka, what are its capabilities and applications.

## What is Kafka
Apache Kafka is a community distributed event streaming platform capable of handling trillions of events a day. Initially conceived as a messaging queue, Kafka is based on an abstraction of a distributed commit log. Since being created and open sourced by LinkedIn in 2011, Kafka has quickly evolved from messaging queue to a full-fledged event streaming platform.

Kafka as streaming platform has three key capabilities:
- Publish and subscribe to streams of records, similar to a message queue or enterprise messaging system.
- Store streams of records in a fault-tolerant durable way.
- Process streams of records as they occur.

Kafka is generally used for two broad classes of applications:
- Building real-time streaming data pipelines that reliably get data between systems or applications
- Building real-time streaming applications that transform or react to the streams of data

## What is Confluent
Founded by the original developers of Apache Kafka, Confluent delivers the most complete distribution of Kafka with Confluent Platform. Confluent Platform improves Kafka with additional community and commercial features designed to enhance the streaming experience of both operators and developers in production, at massive scale.

## Challenge with cloud (AWS)
Provisioning Kafka cluster on AWS can be as simple as installing Java and Confluent Platform packages or in a more professional way, using Chef and Packer, we simply can create an AMI with Kafka and all dependencies installed on that box. But the challenge in the Kafka configuration:
- How do we determine the broker id for each broker?
- How we handle broker replacement? On in other word, how we tell to the other brokers about new broker IP address?
- In the event of new broker initialization, how we manage data replication?

### Assumptions
1. We are having a cluster of 3 brokers
2. Each brokers deployed on an EC2 instance in one Available Zone - AZ
3. We are leveraging Auto Scaling Group - ASG
4. Using [Chef](https://www.chef.io/) and [Packer](https://www.packer.io/) to bake Confluent Kafka and all dependencies
5. Using [Keystore](https://github.com/stelligent/keystore) for secret and configuration management

Now, let's talk about deploying Kafka cluster (Confluent flavor) on AWS as a service. Means, there is no manual installation or configuration, in case of any broker replacement, proper configuration (such as broker id assignment) is automated and no manual configuration needed what so ever!

## Broker assignment
One of the mandatory Kafka properties is broker's `id`. It can be string or number, but it needs to be unique in the cluster. Now the challenge is how we set this value? 
There may be a several way to address this challenge, and I will cover two in this article:
1. **Use EC2 instance id;** it is very simple to setup, but the issue is in case of broker replacement, all replication can put a heavy traffic on the network. Other downside is if all brokers got terminated, we will lose the data. This option seems a viable one for the big cluster.
2. **Use number 0 to N;** it needs some custom code and the idea is to query the Zookeeper, see what id is available (not taken yet), and pick the first one. The script needs to be smart enough to handle multiple request and not to assign duplicate id, however, this may not be a simple task. The main benefit of this option is that we can predict the broker id and provision some resources like EBS and ENI (covered in next section), and apply them to each broker every time. This option is good for small to medium size of cluster. Here is some example in python about how we can manage the broker assignment:
    ```python
    from kazoo.client import KazooClient

    zk = KazooClient(hosts=zk_hosts, logger=logger)
    zk.start()
    zk_broker_ids = zk.get_children('/brokers/ids')
    zk.stop()
    zk.close()
    # our cluster size is 3 in our example
    max_broker_count = 3
    set_broker_ids = set(map(int, zk_broker_ids))
    possible_broker_ids = set(range(max_broker_count))
    broker_id = sorted(possible_broker_ids - set_broker_ids)[0]
    ```

In this article my focus would be on option two with broker ids of 0, 1 and 2.

## ENI attachment

Since we know the broker id, attaching ENI is easy, because we simply can map broker ids with the ENI tags:
1. id = 0 map to ENI tag KAFKA-0
2. id = 1 map to ENI tag KAFKA-1
3. id = 2 map to ENI tag KAFKA-2

Before we go deeper, let's see why we need ENI. We need to create an environment with the static internal IP addresses for the brokers, means if a broker got replaced, the new one get the same IP address. With Elastic Network Interface - ENI, we can manage ENI attachment in a fairly uncomplicated manner.

In ASG launch configuration, we should follow this order to attach the ENI:
1. Get broker id (covered [above](#broker-assignment))
2. Get available ENI with the tag that contains broker id from step 1
    ```ruby
    broker_id = get_broker_id()
    @ec2 = Aws::EC2::Client.new(region: region)
    # get the available eni
    eni = @ec2.describe_network_interfaces(
      filters: [
        { name: 'tag:Name', values: ["KAFKA-#{broker_id}"] },
        { name: 'status', values: ['available'] }
      ]).network_interfaces[0]
    ```
3. Attach the ENI
    ```ruby
    metadata_endpoint = 'http://169.254.169.254/latest/meta-data/'
    instance_id = Net::HTTP.get(URI.parse(metadata_endpoint + 'instance-id'))
    eni.attach(instance_id: instance_id, device_index: 1)
    ```
4. At this point, the new network with the IP address that we know is attached, but we are not able to use it for communication yet! Unless we create a network config and route and make our new network device as the default. This can be managed by this shell script
    ```sh
    #!/bin/bash -e
    export GATEWAY=`route -n | grep "^0.0.0.0" | tr -s " " | cut -f2 -d" "`

    if [ -f /etc/network/interfaces.d/eth1.cfg ]; then mv -f /etc/network/interfaces.d/eth1.cfg /etc/network/interfaces.d/backup.eth1.cfg.backup; fi
    cat > /etc/network/interfaces.d/eth1.cfg <<ETHCFG
    auto eth1
    iface eth1 inet dhcp
        up ip route add default via $GATEWAY dev eth1 table eth1_rt
        up ip rule add from <%= new_ip_address %> lookup eth1_rt prio 1000
    ETHCFG

    mv /etc/iproute2/rt_tables /etc/iproute2/backup.rt_tables.backup
    cat > /etc/iproute2/rt_tables <<RTTABLES
    #
    # reserved values
    #
    255     local
    254     main
    253     default
    0       unspec
    #
    # local
    #
    #1      inr.ruhep
    2 eth1_rt
    RTTABLES

    ifup eth1

    ip route add default via $GATEWAY dev eth1 table eth1_rt;
    ```
These scripts can be run by Chef in the launch configuration.

## EBS attachment
## How to handle service discovery
## Why it is self-healing

### References
- https://kafka.apache.org
- https://www.confluent.io
