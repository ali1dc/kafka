Apache Kafka is a community distributed event streaming/processing platform capable of handling trillions of events a day. Managing Kafka, especially in cloud environments can be a difficult and daunting task. In this blog post, I will address the challenge of deploying Kafka as a Service on AWS; but first, let's see what is Kafka and what are its capabilities and applications.

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
    ```ruby
    require 'zookeeper'
    def get_broker_id(zk_host)
      zk = Zookeeper.new(zk_host)
      assigned_ids = zk.get_children(:path => '/brokers/ids')[:children]
      # our cluster size is 3 in our example
      max_broker_count = 3
      all_ids =* (0..(max_broker_count - 1)).map(&:to_s)
      possible_ids = all_ids - assigned_ids
      possible_ids.size == 0 ? -1 : possible_ids[0]
    end
    ```
2. Get available ENI with the tag that contains broker id from step 1
    ```ruby
    zk_host = '10.100.1.100:2181,10.100.2.100:2181,10.100.3.100:2181'

    broker_id = get_broker_id(zk_host)
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
Next step is attaching EBS volume, but why we need this? The main question is what is going to happen for the data is a broker got terminated or replaced by another one? Are we going to lose the data?
The short answer is no under one condition; `Topic's replication factor`. 

Kafka is a fault tolerant distributed system and it replicates data based on Topic's replication factor. The general formula is if the number of terminated instances (brokers) are equal or grater than number of Topic's replication, then we are going to lose the data. For example, If the replication factor is `1` and you terminate that broker, the data is gone. However, if we set the replication factor to a reasonable number, we protect that data, but the challenge is, every time that a broker got replaced that data need to be replicated over to the new broker and this can put lots of traffic ands stress on out network. (This happens often when we are on cloud. Think as resilient testing with [Chaos Monkey](https://github.com/Netflix/chaosmonkey))

Now, in order to prevent full data replication over the new broker, we can leverage EBS volume attachment technic to attach the same volume based on broker id, over and over. Here is how we can achieve this goal; use an extra EBS volume for each broker and tag it with `KAFKA-#{broker_id}`, set the `Delete on termination` property to `false`, and attach it with the new replaced broker for the data folder. Here is a python code regarding how to do that:
```python
from boto import ec2
import commands

broker_id = get_broker_id()
conn = ec2.connect_to_region(region_name)

volume = conn.get_all_volumes(
  filters = {
    'tag:Name': "KAFKA-%s" % broker_id
  })[0]
# attach the volume
conn.attach_volume(volume.id, instance_id, '/dev/xvdg')
# mount it
commands.getstatusoutput('mount /dev/xvdg /kafkalogs')
```
## How to handle service discovery
Now that we attached an extra network device or Elastic Network Interface, ENI, We can specify, the IP addresses that we want. In the Auto Scaling Group cloudformation template, we can provision ENI with whatever IP that we want in the subnet. Here is the how:
```yaml
NetworkInterface1:
  Type: AWS::EC2::NetworkInterface
  Properties:
    SubnetId:
      Ref: Subnet1
    PrivateIpAddress: 10.100.1.200
    Description: ENI for Kafka broker 0
    GroupSet:
    - Ref: InstanceSecurityGroup
    Tags:
    - Key: Name
      Value: KAFKA-0
```
Now we always are aware of the new broker's IP (or hostname) and we simply can have the connection url. This is the Kafka connection url (AKA `bootstrap-server`) in our example:
```
broker 0: 10.100.1.200:9092
broker 1: 10.100.2.200:9092
broker 2: 10.100.3.200:9092

cluster: 10.100.1.200:9092,10.100.2.200:9092,10.100.3.200:9092
```
## Why it is self-healing
In section [ENI attachment](#eni-attachment), I covered how we can attach a network interface to the broker with the same id and [here](ebs-attachment), I covered how we can attach an EBS volume and reuse it for all brokers with same id in the history of the Kafka cluster. And last but not least, we assume that we leverage Auto Scaling Group for the cluster deployment. Now let's review a case of broker termination:

* Let's assume Kafka broker 0 got terminated
* Because we have Auto Scaling Group, a new broker starts
* From lunch configuration (or userdata) these steps will run:
  1. Available broker id determination from Zookeeper (`0` in this case)
  2. ENI attachment with tag name of `KAFKA-0` (if it is not available yet, wait for a few seconds)
  3. EBS volume attachment with tag name of `KAFKA-0` (if it is not available yet, wait for a few seconds)
* If steps 1, 2, and 3 were successfully ran to completion, then a successful signal will be sent to the cloudformation stack:
    ```sh
    cfn-signal -e 0 --stack $stack_name --resource InstanceAsg --region us-east-1
    ```
* if any of steps 1, 2, or 3 were not successful, then cloudformation stack and ASG consider that node as unhealthy, will terminate that broker, and will continue the process again until it gets a healthy broker with id of `0`

As we can see, there is no manual job what so ever with this way and we can consider this as Self-Healing cluster or Kafka as a Service.

[Here](git@github.com:ali1dc/xd-kafka.git) you can find the source code for the Kafka as a Service configuration, ready for AWS deployment.

### References
- https://kafka.apache.org
- https://www.confluent.io
