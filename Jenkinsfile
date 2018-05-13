#!/usr/bin/env groovy

pipeline {
  agent any
  stages {
    stage('Commit') {
      steps {
        sh 'which bundle || gem install bundler'
        sh 'bundle install'
      }
    }
    stage('Code Analysis') {
      steps {
        rake 'rubocop'
      }
    }
    stage('Kafka AMI') {
      steps {
        sh '''
          # create vendor cookbooks
          whoami
          cd cookbooks/kafka-config/
          pwd
          berks vendor ../vendor-cookbooks
          cd ../..
          pwd
        '''
        sh '''
          # Build AMI with Packer
          #packer build packer/kafka.json
          #ami_id="$(cat manifest.json | jq -r .builds[0].artifact_id | cut -d\':\' -f2)"
          #keystore.rb store --table $inventory_store --kmsid $kms_id --keyname "KAFKA_LATEST_AMI" --value ${ami_id}
        '''
      }
    }
    stage('Deployment') {
      steps {
        sh '''
          echo "start deployment"
          ami_id="$(keystore.rb retrieve --table $inventory_store --keyname KAFKA_LATEST_AMI)"
          echo "deploy this ami: ${ami_id}"
        '''

        // Deploy Kafka
        rake 'deploy'
      }
    }
  }
}

// Helper function for rake
def rake(String command) {
  sh "bundle exec rake $command"
}
