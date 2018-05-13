# frozen_string_literal: true

require 'aws-sdk'
require 'pipeline/cfn_helper'

# Pipeline
module Pipeline
  # Provides helper methods for provisioning
  class CloudFormationHelper
    def aws_region
      return 'us-east-1' if ENV['AWS_REGION'].nil?
      ENV['AWS_REGION']
    end

    def cfn_parameters(template_name)
      template_path = 'provisioning'
      {
        stack_name: stack_name,
        capabilities: %w[CAPABILITY_IAM CAPABILITY_NAMED_IAM],
        template_body: File.read("#{template_path}/#{template_name}.yml"),
        parameters: stack_parameters
      }
    end

    def parameter(key, value)
      {
        parameter_key: key,
        parameter_value: value
      }
    end

    def waiter(waiter_name)
      started_at = Time.now

      @cloudformation.wait_until(waiter_name, stack_name: stack_name) do |w|
        w.max_attempts = nil
        w.before_wait do
          throw :failure if Time.now - started_at > 3600
        end
      end

      sleep 180 if waiter_name == :stack_create_complete
    end

    def stack_exists?
      @cloudformation.describe_stacks(stack_name: stack_name)
      true
    rescue Aws::CloudFormation::Errors::ValidationError
      false
    end
  end
end
