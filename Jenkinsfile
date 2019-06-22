#!/usr/bin/env groovy

pipeline {
  agent any
  parameters {
    choice(
      choices: 'NO\nYES',
      description: 'Do you want to build a new Kafka AMI?',
      name: 'BUILD_AMI')
  }
  stages {

    stage('Commit') {
      steps {
        rvm '2.5.3'
      }
    }

    stage('Code Analysis') {
      steps {
        // rake 'rubocop'
        echo 'run rubocop later'
      }
    }

    stage('Kafka AMI') {
      when {
        expression { params.BUILD_AMI == 'YES' }
      }
      steps {
        echo 'Create Vendor Cookbooks'
        sh '''
          cd cookbooks/kafka-config/
          berks vendor ../vendor-cookbooks
          cd ../..
        '''
        echo 'Build AMI with Packer'
        sh 'packer build packer/kafka.json'
        echo 'Store Kafka AMI'
        sh '''
          ami_id="$(cat manifest.json | jq -r .builds[0].artifact_id | cut -d\':\' -f2)"
          keystore.rb store --table $inventory_store --kmsid $kms_id --keyname "KAFKA_LATEST_AMI" --value ${ami_id}
        '''
      }
    }

    stage('Deployment') {
      steps {
        // echo 'Start deploying "$(keystore.rb retrieve --table $inventory_store --keyname KAFKA_LATEST_AMI)"'
        // Deploy Kafka
        rake 'deploy'
      }
    }
  }
}

// Helper function for rake
def rake(String command) {
  sh returnStdout: false, script: """#!/bin/bash --login
    source /usr/share/rvm/scripts/rvm && \
      rvm use --install --create 2.5.3 && \
      export | egrep -i "(ruby|rvm)" > rvm.env
    rvm use default 2.5.3
    rvm alias create default ruby-2.5.3
    bundle exec rake $command
  """
}

def rvm(String version) {
  sh returnStdout: false, script: """#!/bin/bash --login
    source /usr/share/rvm/scripts/rvm && \
      rvm use --install --create ${version} && \
      export | egrep -i "(ruby|rvm)" > rvm.env
    rvm use default ${version}
    rvm alias create default ruby-${version}
    which bundle || gem install bundler -v 1.17.3
    bundle install
  """
}
