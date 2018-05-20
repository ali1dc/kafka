#!/usr/bin/env groovy

pipeline {
  agent any
  parameters {
    choice(
      choices: 'YES\nNO',
      description: 'Build AMI feature toggle',
      name: 'BUILD_AMI')
  }
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
        echo "Start deploying $(keystore.rb retrieve --table $inventory_store --keyname KAFKA_LATEST_AMI)"
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
