# frozen_string_literal: true

require 'aws-sdk'
require 'keystore'

# Pipeline
module Pipeline
  # Keystore wrapper class
  class Keystore
    attr_accessor(:keystore)

    def initialize
      # internal module variable cache of keystore retrieval results
      @keystore_cache = {}

      @client_config = { region: 'us-east-1' }
    end

    # Setup the class variables needed for keystore access
    def setup_keystore
      %w[inventory_store kms_id].each do |key|
        raise "Missing environment variable: #{key}" unless ENV[key]
      end
      dynamo = ::Aws::DynamoDB::Client.new(**@client_config)
      kms = ::Aws::KMS::Client.new(**@client_config)
      @keystore = ::Keystore.new dynamo: dynamo, kms: kms, key_alias: nil,
                                 table_name: ENV['inventory_store'],
                                 key_id: ENV['kms_id']
    end

    def query(keyname, use_cache: true)
      return @keystore_cache[keyname] if \
        @keystore_cache.key?(keyname) && use_cache
      setup_keystore unless @keystore
      @keystore_cache[keyname] = @keystore.retrieve(key: keyname)
    end

    alias query? query

    # Set a value in keystore
    def save(key, value)
      # Pipeline.logger.debug "Storing #{key} as #{value}"
      setup_keystore unless @keystore
      res = @keystore.store(key: key,
                            value: value)
      # Pipeline.logger.debug res.inspect
      puts res.inspect
    end
  end
end
