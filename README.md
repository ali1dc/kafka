Apache Kafka
=========

This repository contains the Chef, Packer, and Jenkins
code necessary for a Kafka pipeline to deploy Kafka (Confluent flavour) in stateless mode or Kafka as a Service.

## What is Kafka
Apache Kafka is a community distributed event streaming platform capable of handling trillions of events a day. Initially conceived as a messaging queue, Kafka is based on an abstraction of a distributed commit log. Since being created and open sourced by LinkedIn in 2011, Kafka has quickly evolved from messaging queue to a full-fledged event streaming platform.

## What is Confluent
Founded by the original developers of Apache Kafka, [Confluent](https://confluent.io) delivers the most complete distribution of Kafka with Confluent Platform. Confluent Platform improves Kafka with additional community and commercial features designed to enhance the streaming experience of both operators and developers in production, at massive scale.

## Bootstrap Server Url: 
```
10.100.1.200:9092,10.100.2.200:9092,10.100.3.200:9092
```

## How to use it
1. Download and install [Confluent Platform](https://docs.confluent.io/current/installation/installing_cp/zip-tar.html#prod-kafka-cli-install)
2. Set some environment variables:
    ```sh
    export zk=10.100.1.100:2181,10.100.2.100:2181,10.100.3.100:2181
    export kafka=10.100.1.200:9092,10.100.2.200:9092,10.100.3.200:9092
    ```
3. Now you can start!

## Run in locally
1. Run [Zookeeper](https://github.com/ali1dc/xd-zookeeper#run-in-locally)
2. Run Kafka locally:
    ```sh
    $ docker-compose up
    ```
3. Run some commands:
    ```sh
    # list of topics:
    ./kafka-topics --bootstrap-server broker:9092 --list
    
    # create a topic:
    ./kafka-topics --bootstrap-server broker:9092 --create --topic my-test --partitions 1 --replication-factor 1
    
    # produce message/event to a topic:
    ./kafka-console-producer --broker-list broker:9092 --topic my-test
    # this will open a socket, and each line would be an event

    # consume messages from a topic:
    ./kafka-console-consumer --bootstrap-server broker:9092 --topic my-test --from-beginning
    
    # if you want to the messages from beginning:
    ./kafka-console-consumer --bootstrap-server broker:9092 --topic my-test --from-beginning

    # delete a topic
    ./kafka-topics --bootstrap-server broker:9092 --delete --topic my-test
    ```

## Tech Stack
- AWS
  - EC2 / ASG
  - EBS
  - ENI - Elastic Network Interface
  - Cloudformation
  - AMI
- Chef
- Packer
- Jenkins
- [Keystore](https://github.com/stelligent/keystore) for secret and configuration management

## Requirements
1. Zookeeper; Check [this](https://github.com/ali1dc/xd-zookeeper) repository
2. Following keystore keys are expected:
    * VPC\_ID - String VPC ID to deploy into
    * PRIVATE\_SUBNET\_1 - subnet id to deploy to
    * PRIVATE\_SUBNET\_2 - subnet id to deploy to
    * PRIVATE\_SUBNET\_3 - subnet id to deploy to
    * KAFKA_LATEST_AMI - kafka ami id from packer
    * SSH\_KEYNAME - EC2 ssh keyname for sshing purposes
    * PRIVATE\_SECURITY\_GROUP - AWS security group id
