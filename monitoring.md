In part 1, we covered how we can automate Zookeeper and deploy it as a services, in part 2, we discussed about how we can deploy Apache Kafka on AWS in a fully automated and self-healing manner. Now let's talk about operation! The challenge is, now we have fully automated Zookeeper and Kafka, how we can monitor the cluster? How do we know is a simple way about the number of healthy Kafka brokers or Zookeeper nodes?

With [Confluent Platform Enterprise](https://www.confluent.io/product/confluent-platform/) there is a monitoring tool called [Control Center](https://www.confluent.io/confluent-control-center/) you get a very cool dashboard for monitoring and managing Kafka, Zookeeper and other Confluent tools. However Control Center is not free and it is somehow pricey!

In this blog post, I am going to show you step-by-step how you can achieve have a very cool monitoring dashboard with all open source products.

### Requirements
Here is the list of tools that we need to achieve our goal:
1. [Prometheus](https://prometheus.io); an open-source systems monitoring and alerting toolkit originally built at SoundCloud.
2. [Node Exporter](https://github.com/prometheus/node_exporter); for hardware and OS metrics with pluggable metric collectors. It allows to measure various machine resources such as memory, disk and CPU utilization.
3. [Grafana](https://grafana.com/); an open source metric analytics & visualization suite. It is most commonly used for visualizing time series data for infrastructure and application analytics but many use it in other domains including industrial sensors, home automation, weather, and process control.

Now let's dive on each tool and talk about how we can set them up.

## Prometheus
First thing we need is an EC2 instance, create an Ubuntu 16.04 EC2 instance on AWS and ssh into it.

Now we are ready to install and configure the Prometheus:

### Downloading Prometheus
From the Prometheus [download](https://prometheus.io/download/) page, download and setup the latest stable version:
```sh
$ wget https://github.com/prometheus/prometheus/releases/download/v2.11.1/prometheus-2.11.1.linux-amd64.tar.gz

# compare the checksum
$ sha256sum prometheus-2.11.1.linux-amd64.tar.gz

# untar 
$ tar xvf prometheus-2.11.1.linux-amd64.tar.gz
```
### Creating users and service
```sh
# create prometheus user
$ sudo useradd --no-create-home --shell /bin/false prometheus

# create the necessary directories
$ sudo mkdir /etc/prometheus
$ sudo chown prometheus:prometheus /etc/prometheus
$ sudo mkdir /var/lib/prometheus
$ sudo chown prometheus:prometheus /var/lib/prometheus
```

### Setting Prometheus up
```sh
# copy the binary files to the bin folder
$ sudo cp prometheus-2.11.1.linux-amd64/prometheus /usr/local/bin/
$ sudo cp prometheus-2.11.1.linux-amd64/promtool /usr/local/bin/

# change tht ownership to prometheus user
$ sudo chown prometheus:prometheus /usr/local/bin/prometheus
$ sudo chown prometheus:prometheus /usr/local/bin/promtool

# set consoles and console_libraries
$ sudo cp -r prometheus-2.11.1.linux-amd64/consoles /etc/prometheus
$ sudo chown -R prometheus:prometheus /etc/prometheus/consoles
$ sudo cp -r prometheus-2.11.1.linux-amd64/console_libraries /etc/prometheus
$ sudo chown -R prometheus:prometheus /etc/prometheus/console_libraries

# cleanup
rm -rf rm -rf prometheus-2.11.1.linux-amd64*
```
### Configuring Prometheus
Create `prometheus.yml` file in the folder `/etc/prometheus` and copy this content:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    scrape_interval: 5s
    static_configs:
      - targets: ['localhost:9090']
```

Now change the ownership of the file to newly created user `prometheus`:
```sh
$ sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
```

### Running Prometheus
Create `prometheus.service` file in the folder `/etc/systemd/system` and copy this content:
```
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
    --config.file /etc/prometheus/prometheus.yml \
    --storage.tsdb.path /var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
```
 Reload systemd by running:
```sh
$ sudo systemctl daemon-reload
``` 
Finally, enable and start the service on boot:

```sh
$ sudo systemctl start prometheus
$ sudo systemctl enable prometheus
```

Now if you browse to the host with port `9090` (http://<ec2_ip_address>:9090) you should see the Prometheus page.

**Please note;** Prometheus does not have built-in authentication, instead you can use `nginx` to add basic HTTP authentication.

## Node Exporter
For collecting metrics from any EC2 instances such as Kafka brokers and Zookeeper nodes, we need to install `Node Exporter`. We can use [this cookbook](https://supermarket.chef.io/cookbooks/prometheus-platform) to automate the process of installation. However for simplicity, I will show you how to install it by some shell command:

### Step 1: Create User
```sh
$ sudo useradd --no-create-home --shell /bin/false node_exporter
```

### Step 2: Download & Install the Node Exporter

Download the current stable version of Node Exporter from [here](https://github.com/prometheus/node_exporter/releases)
```sh
$  wget https://github.com/prometheus/node_exporter/releases/download/v0.18.1/node_exporter-0.18.1.linux-amd64.tar.gz

# compare the checksum
$ sha256sum node_exporter-0.18.1.linux-amd64.tar.gz

# untar
$ tar xvf node_exporter-0.18.1.linux-amd64.tar.gz

# copy the binary to the /usr/local/bin and set the ownership
$ sudo cp node_exporter-0.18.1.linux-amd64/node_exporter /usr/local/bin/
$ sudo chown node_exporter:node_exporter /usr/local/bin/node_exporter

# cleanup
$ rm -rf node_exporter-0.18.1.linux-amd64*
```

### Step 3: Running Node Exporter as Service
Create the file `node_exporter.service` under the `/etc/systemd/system/` folder with this content:
```
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.listen-address=":7072"

[Install]
WantedBy=multi-user.target
```
Reload systemd
```sh
$ sudo systemctl daemon-reload
```
Finally, enable and start the service on boot:
```sh
$ sudo systemctl start node_exporter
$ sudo systemctl enable node_exporter
```

Alright, at this point, we can assume that the node exporter is running on all Zookeeper and Kafka brokers. In the following I am going to cover the Zookeeper and Kafka configuration for Prometheus and Node Exporter.

## Server Metrics
There are 2 kind on Metrics we should collect from Kafka brokers:

1. Internal metrics: JMX specific metrics, the default reporter, though we can add any pluggable reporter. Example: PartitionCount, UnderReplicatedPartitions, and OfflinePartitionsCount. Check [here](https://docs.confluent.io/current/kafka/monitoring.html) for the full list.  
2. Node Exporter metrics: hardware and operating system specific metrics, such as CPU, network and memory utilization. 

### Kafka Configuration 

