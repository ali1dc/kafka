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

## Challenge maintaining Kafka in Cloud (AWS)
## Broker assignment 
## ENI attachment
## EBS attachment 
## How to handle service discovery
## Why it is self-healing

### References
- https://kafka.apache.org
- https://www.confluent.io