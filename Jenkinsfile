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
        sh '''
          rvm use default 2.5.3
          which bundle || gem install bundler -v 1.17.3
          bundle install
        '''
      }
    }

    stage('Code Analysis') {
      steps {
        rake 'rubocop'
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
  sh "bundle exec rake $command"
}
